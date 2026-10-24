from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from app.db.models import Execution
from app.domain.hashing import sha256_canonical
from app.m5_evaluation import M5EvaluationModule
from app.services import ValidationError
from tests.test_api import context_payload, project_payload
from tests.test_m2_ingestion import _contract_ref
from tests.test_m4_modeling import _create_m4_inputs, _m4_request


def _schemas():
    contract_root = Path(__file__).parents[2] / "contracts"
    if not contract_root.is_dir():
        contract_root = Path(__file__).parents[1] / "contracts"
    schemas = {}
    for path in contract_root.rglob("*.json"):
        schema = json.loads(path.read_text(encoding="utf-8"))
        schemas[schema["$id"]] = schema
    registry = Registry().with_resources(
        (uri, Resource.from_contents(schema)) for uri, schema in schemas.items()
    )
    return schemas, registry


def _assert_m5_output_contract(result: dict) -> None:
    schemas, registry = _schemas()
    Draft202012Validator(
        schemas["https://analytixflow.local/contracts/m5/output.schema.json"],
        registry=registry,
    ).validate(result)


def _m5_request(project, context, gold, pipeline, *, execution_id: str, key: str):
    return {
        "project_id": project["id"],
        "execution_id": execution_id,
        "module_id": "m5",
        "contract_version": "v1.0",
        "context_snapshot_id": context["id"],
        "status": "requested",
        "correlation_id": f"corr-{execution_id}",
        "idempotency_key": key,
        "module_input": {
            "candidate_models": [_contract_ref(pipeline)],
            "gold_dataset": _contract_ref(gold),
            "baseline": {
                "description": "Use the persisted majority-class baseline.",
                "artifact_or_method": "majority_class_baseline",
            },
            "evaluation_policy": {
                "primary_metrics": ["f1_macro"],
                "secondary_metrics": ["accuracy"],
                "validation_strategy": "holdout",
                "bias_checks": ["review_subgroup_definition"],
            },
            "success_criteria": ["Human review of the measured comparison is required."],
        },
    }


def _approve_candidate(client, project, pipeline):
    approval = client.post(
        f"/api/v1/projects/{project['id']}/approvals",
        json={
            "action": "select_model_candidate",
            "scope_type": "artifact",
            "artifact_id": pipeline["artifact_id"],
            "artifact_version": pipeline["artifact_version"],
            "requested_by": "m5-reviewer",
        },
    )
    assert approval.status_code == 201
    approval_data = approval.json()
    resolved = client.post(
        f"/api/v1/projects/{project['id']}/approvals/{approval_data['id']}/resolve",
        json={"status": "approved", "resolved_by": "m5-approver"},
    )
    assert resolved.status_code == 200
    resolved_data = resolved.json()
    return {
        "approval_id": resolved_data["id"],
        "action": resolved_data["action"],
        "scope_type": resolved_data["scope_type"],
        "status": resolved_data["status"],
        "scope_hash": resolved_data["scope_hash"],
        "artifact_id": resolved_data["artifact_id"],
        "artifact_version": resolved_data["artifact_version"],
        "approved_by": resolved_data["resolved_by"],
        "approved_at": resolved_data["resolved_at"],
    }


def _create_m4_result(client, project, context):
    gold, problem = _create_m4_inputs(client, project)
    m4 = client.post(
        f"/api/v1/projects/{project['id']}/executions/m4",
        json=_m4_request(
            project,
            context,
            gold,
            problem,
            execution_id="m4-for-m5",
            key="m4-for-m5-key",
        ),
    )
    assert m4.status_code == 200
    result = m4.json()
    pipeline = next(
        item["pipeline_artifact"]
        for item in result["module_output"]["candidates"]
        if item["technique"] == "logistic_regression"
    )
    return gold, pipeline


def test_m5_reviews_persisted_m4_evidence_and_requires_human_approval(client):
    project = client.post("/api/v1/projects", json=project_payload()).json()
    context = client.post(
        f"/api/v1/projects/{project['id']}/context", json=context_payload("m5")
    ).json()
    gold, pipeline = _create_m4_result(client, project, context)

    request = _m5_request(
        project,
        context,
        gold,
        pipeline,
        execution_id="m5-execution-1",
        key="m5-key-1",
    )
    request["approval_refs"] = [_approve_candidate(client, project, pipeline)]
    request["approval_refs"][0]["approved_by"] = "forged-client-value"
    response = client.post(
        f"/api/v1/projects/{project['id']}/executions/m5", json=request
    )
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "awaiting_approval"
    _assert_m5_output_contract(result)
    assert result["module_output"]["recommendation"]["status"] == "insufficient_evidence"
    assert result["module_output"]["decision_request"] == {
        "action": "record_insufficient_evidence",
        "requires_approval": True,
    }
    assert result["approval_refs"][0]["approved_by"] == "m5-approver"
    assert result["module_output"]["evaluation_report"]["layer"] == "report"
    assert result["module_output"]["model_comparisons"][0]["metrics"][
        "result_classification"
    ] == "measured"

    replay = client.post(
        f"/api/v1/projects/{project['id']}/executions/m5", json=request
    )
    assert replay.status_code == 200
    assert replay.json() == result


def test_m5_rejects_candidate_from_another_project(client):
    first = client.post("/api/v1/projects", json=project_payload()).json()
    second = client.post("/api/v1/projects", json=project_payload()).json()
    first_context = client.post(
        f"/api/v1/projects/{first['id']}/context", json=context_payload("first-m5")
    ).json()
    second_context = client.post(
        f"/api/v1/projects/{second['id']}/context", json=context_payload("second-m5")
    ).json()
    gold, pipeline = _create_m4_result(client, first, first_context)
    request = _m5_request(
        second,
        second_context,
        gold,
        pipeline,
        execution_id="m5-cross-project",
        key="m5-cross-project-key",
    )
    request["approval_refs"] = [_approve_candidate(client, first, pipeline)]
    response = client.post(
        f"/api/v1/projects/{second['id']}/executions/m5", json=request
    )
    assert response.status_code == 404


def test_m5_rejects_metric_missing_from_persisted_m4_evidence(client):
    project = client.post("/api/v1/projects", json=project_payload()).json()
    context = client.post(
        f"/api/v1/projects/{project['id']}/context", json=context_payload("m5-metric")
    ).json()
    gold, pipeline = _create_m4_result(client, project, context)
    request = _m5_request(
        project,
        context,
        gold,
        pipeline,
        execution_id="m5-missing-metric",
        key="m5-missing-metric-key",
    )
    request["module_input"]["evaluation_policy"]["primary_metrics"] = ["roc_auc"]
    request["approval_refs"] = [_approve_candidate(client, project, pipeline)]
    response = client.post(
        f"/api/v1/projects/{project['id']}/executions/m5", json=request
    )
    assert response.status_code == 422
    assert "Requested metrics are missing" in response.json()["detail"]


def test_m5_reviews_regression_evidence_with_lower_is_better_metrics(client):
    project = client.post("/api/v1/projects", json=project_payload()).json()
    context = client.post(
        f"/api/v1/projects/{project['id']}/context", json=context_payload("m5-regression")
    ).json()
    gold, problem = _create_m4_inputs(
        client,
        project,
        problem_content=b'{"problem_type":"regression","target":"amount"}',
    )
    m4_payload = _m4_request(
        project,
        context,
        gold,
        problem,
        execution_id="m4-for-m5-regression",
        key="m4-for-m5-regression-key",
    )
    m4_payload["module_input"]["target_column"] = "amount"
    m4_payload["module_input"]["model_policy"] = {
        "problem_type": "regression",
        "allowed_techniques": ["linear_regression"],
    }
    m4 = client.post(
        f"/api/v1/projects/{project['id']}/executions/m4", json=m4_payload
    )
    assert m4.status_code == 200
    m4_result = m4.json()
    pipeline = next(
        item["pipeline_artifact"]
        for item in m4_result["module_output"]["candidates"]
        if item["technique"] == "linear_regression"
    )
    request = _m5_request(
        project,
        context,
        gold,
        pipeline,
        execution_id="m5-regression",
        key="m5-regression-key",
    )
    request["module_input"]["baseline"]["artifact_or_method"] = "mean_baseline"
    request["module_input"]["evaluation_policy"] = {
        "primary_metrics": ["rmse"],
        "secondary_metrics": ["mae", "r2"],
        "validation_strategy": "holdout",
    }
    request["approval_refs"] = [_approve_candidate(client, project, pipeline)]
    result = client.post(
        f"/api/v1/projects/{project['id']}/executions/m5", json=request
    )
    assert result.status_code == 200
    assert result.json()["status"] == "awaiting_approval"
    _assert_m5_output_contract(result.json())
    assert result.json()["module_output"]["model_comparisons"][0]["baseline_comparison"][
        "direction"
    ] == "lower_is_better"


def test_m5_reviews_descriptive_measured_profile(client):
    project = client.post("/api/v1/projects", json=project_payload()).json()
    context = client.post(
        f"/api/v1/projects/{project['id']}/context", json=context_payload("m5-descriptive")
    ).json()
    gold, problem = _create_m4_inputs(
        client, project, problem_content=b'{"problem_type":"descriptive"}'
    )
    m4_payload = _m4_request(
        project,
        context,
        gold,
        problem,
        execution_id="m4-for-m5-descriptive",
        key="m4-for-m5-descriptive-key",
    )
    m4_payload["module_input"].pop("target_column")
    m4_payload["module_input"]["model_policy"] = {
        "problem_type": "descriptive",
        "allowed_techniques": ["descriptive_statistics"],
    }
    m4 = client.post(
        f"/api/v1/projects/{project['id']}/executions/m4", json=m4_payload
    )
    assert m4.status_code == 200
    pipeline = m4.json()["module_output"]["candidates"][0]["pipeline_artifact"]
    request = _m5_request(
        project,
        context,
        gold,
        pipeline,
        execution_id="m5-descriptive",
        key="m5-descriptive-key",
    )
    request["module_input"]["baseline"]["artifact_or_method"] = "descriptive_statistics"
    request["module_input"]["evaluation_policy"] = {
        "primary_metrics": ["row_count"],
        "secondary_metrics": ["column_count"],
        "validation_strategy": "holdout",
    }
    request["approval_refs"] = [_approve_candidate(client, project, pipeline)]
    result = client.post(
        f"/api/v1/projects/{project['id']}/executions/m5", json=request
    )
    assert result.status_code == 200
    assert result.json()["status"] == "awaiting_approval"
    _assert_m5_output_contract(result.json())


def test_m5_rejects_evaluation_without_candidate_approval(client):
    project = client.post("/api/v1/projects", json=project_payload()).json()
    context = client.post(
        f"/api/v1/projects/{project['id']}/context", json=context_payload("m5-no-approval")
    ).json()
    gold, pipeline = _create_m4_result(client, project, context)
    request = _m5_request(
        project,
        context,
        gold,
        pipeline,
        execution_id="m5-no-approval",
        key="m5-no-approval-key",
    )
    response = client.post(
        f"/api/v1/projects/{project['id']}/executions/m5", json=request
    )
    assert response.status_code == 422
    assert any(
        "approval_refs" in item.get("loc", [])
        for item in response.json()["detail"]
    )


def test_m5_rejects_non_finite_and_out_of_domain_metrics():
    with pytest.raises(ValidationError, match="not finite"):
        M5EvaluationModule._validate_measured_results(
            {
                "result_classification": "measured",
                "metrics": {"f1_macro": float("nan")},
                "primary_metric": "f1_macro",
            },
            "classification",
            "candidate",
        )
    with pytest.raises(ValidationError, match=r"outside \[0, 1\]"):
        M5EvaluationModule._validate_measured_results(
            {
                "result_classification": "measured",
                "metrics": {"f1_macro": 1.1},
                "primary_metric": "f1_macro",
            },
            "classification",
            "candidate",
        )


def test_m5_rejects_inconsistent_persisted_baseline_comparison(client):
    project = client.post("/api/v1/projects", json=project_payload()).json()
    context = client.post(
        f"/api/v1/projects/{project['id']}/context", json=context_payload("m5-baseline")
    ).json()
    gold, pipeline = _create_m4_result(client, project, context)
    with client.app.state.session_factory() as db:
        execution = db.get(Execution, "m4-for-m5")
        corrupted = deepcopy(execution.result_json)
        candidate = next(
            item
            for item in corrupted["module_output"]["candidates"]
            if item["technique"] == "logistic_regression"
        )
        candidate["preliminary_results"]["baseline_comparison"][
            "baseline_candidate_id"
        ] = "not-the-declared-baseline"
        execution.result_json = corrupted
        db.commit()

    request = _m5_request(
        project,
        context,
        gold,
        pipeline,
        execution_id="m5-inconsistent-baseline",
        key="m5-inconsistent-baseline-key",
    )
    request["approval_refs"] = [_approve_candidate(client, project, pipeline)]
    response = client.post(
        f"/api/v1/projects/{project['id']}/executions/m5", json=request
    )
    assert response.status_code == 422
    assert "M4 execution result hash" in response.json()["detail"]

    with client.app.state.session_factory() as db:
        execution = db.get(Execution, "m4-for-m5")
        execution.output_hash = sha256_canonical(execution.result_json)
        db.commit()

    request["execution_id"] = "m5-inconsistent-baseline-checked"
    request["idempotency_key"] = "m5-inconsistent-baseline-checked-key"
    response = client.post(
        f"/api/v1/projects/{project['id']}/executions/m5", json=request
    )
    assert response.status_code == 422
    assert "Baseline comparison is inconsistent" in response.json()["detail"]
