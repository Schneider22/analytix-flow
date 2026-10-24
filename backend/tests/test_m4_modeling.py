from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from tests.test_api import context_payload, project_payload
from tests.test_m2_ingestion import _contract_ref


def _assert_m4_output_contract(result: dict) -> None:
    contract_root = Path(__file__).parents[2] / "contracts"
    if not contract_root.is_dir():
        contract_root = Path(__file__).parents[1] / "contracts"
    assert contract_root.is_dir(), f"contracts directory not found near {__file__}"
    schemas = {}
    for path in contract_root.rglob("*.json"):
        schema = json.loads(path.read_text(encoding="utf-8"))
        schemas[schema["$id"]] = schema
    registry = Registry().with_resources(
        (uri, Resource.from_contents(schema)) for uri, schema in schemas.items()
    )
    output_schema = schemas["https://analytixflow.local/contracts/m4/output.schema.json"]
    Draft202012Validator(output_schema, registry=registry).validate(result)


def _create_m4_inputs(
    client, project, *, problem_content=b'{"problem_type":"classification","target":"label"}'
):
    gold = client.post(
        f"/api/v1/projects/{project['id']}/artifacts/content",
        params={
            "artifact_type": "dataset.gold",
            "artifact_version": "v1",
            "artifact_id": "orders-gold",
            "media_type": "text/csv",
            "layer": "gold",
            "produced_by_module": "m3",
        },
        content=(
            b"amount,region,label\n"
            b"10,north,no\n"
            b"11,north,no\n"
            b"12,north,no\n"
            b"13,north,no\n"
            b"20,south,yes\n"
            b"21,south,yes\n"
            b"22,south,yes\n"
            b"23,south,yes\n"
        ),
    )
    assert gold.status_code == 201
    problem = client.post(
        f"/api/v1/projects/{project['id']}/artifacts/content",
        params={
            "artifact_type": "problem.definition",
            "artifact_version": "v1",
            "artifact_id": "problem-definition",
            "media_type": "application/json",
            "layer": "other",
            "produced_by_module": "m1",
        },
        content=problem_content,
    )
    assert problem.status_code == 201
    return gold.json(), problem.json()


def _m4_request(project, context, gold, problem, *, execution_id: str, key: str):
    return {
        "project_id": project["id"],
        "execution_id": execution_id,
        "module_id": "m4",
        "contract_version": "v1.0",
        "context_snapshot_id": context["id"],
        "status": "requested",
        "correlation_id": f"corr-{execution_id}",
        "idempotency_key": key,
        "module_input": {
            "gold_dataset": _contract_ref(gold),
            "problem_definition": _contract_ref(problem),
            "target_column": "label",
            "model_policy": {
                "problem_type": "classification",
                "allowed_techniques": ["logistic_regression"],
                "interpretability_constraints": ["prefer_interpretable_candidates"],
            },
            "split_policy": {
                "strategy": "holdout",
                "test_fraction": 0.25,
            },
            "reproducibility": {"random_seed": 17, "record_environment": True},
        },
    }


def test_m4_builds_reproducible_candidates_and_requires_selection_approval(client):
    project = client.post("/api/v1/projects", json=project_payload()).json()
    context = client.post(
        f"/api/v1/projects/{project['id']}/context", json=context_payload("m4")
    ).json()
    gold, problem = _create_m4_inputs(client, project)
    request = _m4_request(
        project,
        context,
        gold,
        problem,
        execution_id="m4-execution-1",
        key="m4-key-1",
    )

    response = client.post(
        f"/api/v1/projects/{project['id']}/executions/m4", json=request
    )
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "succeeded"
    _assert_m4_output_contract(result)
    assert len(result["module_output"]["experiment_artifacts"]) == 1
    assert {item["technique"] for item in result["module_output"]["candidates"]} == {
        "majority_class_baseline",
        "logistic_regression",
    }
    assert all(
        item["preliminary_results"]["result_classification"] == "measured"
        for item in result["module_output"]["candidates"]
    )
    assert result["module_output"]["selection_request"]["requires_approval"] is True
    assert result["next_actions"] == [
        {
            "action": "select_model_candidate",
            "requires_approval": True,
            "target_module": "m5",
        }
    ]

    pipeline = result["module_output"]["candidates"][1]["pipeline_artifact"]
    approval = client.post(
        f"/api/v1/projects/{project['id']}/approvals",
        json={
            "action": "select_model_candidate",
            "scope_type": "artifact",
            "artifact_id": pipeline["artifact_id"],
            "artifact_version": pipeline["artifact_version"],
            "requested_by": "test-reviewer",
        },
    )
    assert approval.status_code == 201

    replay = client.post(
        f"/api/v1/projects/{project['id']}/executions/m4", json=request
    )
    assert replay.status_code == 200
    assert replay.json() == result


def test_m4_supports_regression_with_measured_candidates(client):
    project = client.post("/api/v1/projects", json=project_payload()).json()
    context = client.post(
        f"/api/v1/projects/{project['id']}/context", json=context_payload("m4-regression")
    ).json()
    gold, problem = _create_m4_inputs(
        client, project, problem_content=b'{"problem_type":"regression","target":"amount"}'
    )
    request = _m4_request(
        project,
        context,
        gold,
        problem,
        execution_id="m4-regression",
        key="m4-regression-key",
    )
    request["module_input"]["target_column"] = "amount"
    request["module_input"]["model_policy"] = {
        "problem_type": "regression",
        "allowed_techniques": ["linear_regression"],
    }
    response = client.post(
        f"/api/v1/projects/{project['id']}/executions/m4", json=request
    )
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "succeeded"
    _assert_m4_output_contract(result)
    assert {item["technique"] for item in result["module_output"]["candidates"]} == {
        "mean_baseline",
        "linear_regression",
    }
    assert all(
        item["preliminary_results"]["result_classification"] == "measured"
        for item in result["module_output"]["candidates"]
    )


def test_m4_repeats_same_seed_with_reproducible_measures(client):
    project = client.post("/api/v1/projects", json=project_payload()).json()
    context = client.post(
        f"/api/v1/projects/{project['id']}/context", json=context_payload("m4-repeat")
    ).json()
    gold, problem = _create_m4_inputs(client, project)
    first_request = _m4_request(
        project,
        context,
        gold,
        problem,
        execution_id="m4-repeat-1",
        key="m4-repeat-key-1",
    )
    first = client.post(
        f"/api/v1/projects/{project['id']}/executions/m4", json=first_request
    )
    assert first.status_code == 200
    first_result = first.json()

    second_request = deepcopy(first_request)
    second_request["execution_id"] = "m4-repeat-2"
    second_request["idempotency_key"] = "m4-repeat-key-2"
    second_request["correlation_id"] = "corr-m4-repeat-2"
    second = client.post(
        f"/api/v1/projects/{project['id']}/executions/m4", json=second_request
    )
    assert second.status_code == 200
    second_result = second.json()

    first_candidates = first_result["module_output"]["candidates"]
    second_candidates = second_result["module_output"]["candidates"]
    def measured(candidate):
        result = deepcopy(candidate["preliminary_results"])
        result["baseline_comparison"].pop("baseline_candidate_id", None)
        return result

    assert [measured(item) for item in first_candidates] == [
        measured(item) for item in second_candidates
    ]
    assert [item["pipeline_artifact"]["content_hash"] for item in first_candidates] == [
        item["pipeline_artifact"]["content_hash"] for item in second_candidates
    ]
    assert [item["parameter_artifact"]["content_hash"] for item in first_candidates] == [
        item["parameter_artifact"]["content_hash"] for item in second_candidates
    ]


def test_m4_rejects_techniques_outside_the_project_policy(client):
    project = client.post("/api/v1/projects", json=project_payload()).json()
    context = client.post(
        f"/api/v1/projects/{project['id']}/context", json=context_payload("m4-policy")
    ).json()
    gold, problem = _create_m4_inputs(client, project)
    request = _m4_request(
        project,
        context,
        gold,
        problem,
        execution_id="m4-policy",
        key="m4-policy-key",
    )
    request["module_input"]["model_policy"]["allowed_techniques"] = ["random_forest"]
    response = client.post(
        f"/api/v1/projects/{project['id']}/executions/m4", json=request
    )
    assert response.status_code == 422
    assert "Unsupported M4 techniques" in response.json()["detail"]


def test_m4_rejects_incoherent_problem_definition(client):
    project = client.post("/api/v1/projects", json=project_payload()).json()
    context = client.post(
        f"/api/v1/projects/{project['id']}/context", json=context_payload("m4-definition")
    ).json()
    gold, problem = _create_m4_inputs(client, project)
    request = _m4_request(
        project,
        context,
        gold,
        problem,
        execution_id="m4-definition",
        key="m4-definition-key",
    )
    request["module_input"]["target_column"] = "amount"
    request["module_input"]["model_policy"] = {
        "problem_type": "regression",
        "allowed_techniques": ["linear_regression"],
    }
    response = client.post(
        f"/api/v1/projects/{project['id']}/executions/m4", json=request
    )
    assert response.status_code == 422
    assert "problem_type does not match" in response.json()["detail"]


def test_m4_rejects_gold_artifact_from_another_project(client):
    first = client.post("/api/v1/projects", json=project_payload()).json()
    second = client.post("/api/v1/projects", json=project_payload()).json()
    first_context = client.post(
        f"/api/v1/projects/{first['id']}/context", json=context_payload("first-m4")
    ).json()
    second_context = client.post(
        f"/api/v1/projects/{second['id']}/context", json=context_payload("second-m4")
    ).json()
    gold, problem = _create_m4_inputs(client, first)
    request = _m4_request(
        second,
        second_context,
        gold,
        problem,
        execution_id="m4-cross-project",
        key="m4-cross-project-key",
    )
    response = client.post(
        f"/api/v1/projects/{second['id']}/executions/m4", json=request
    )
    assert response.status_code == 404


def test_m4_supports_descriptive_analytics_without_target(client):
    project = client.post("/api/v1/projects", json=project_payload()).json()
    context = client.post(
        f"/api/v1/projects/{project['id']}/context", json=context_payload("m4-descriptive")
    ).json()
    gold, problem = _create_m4_inputs(
        client, project, problem_content=b'{"problem_type":"descriptive"}'
    )
    request = _m4_request(
        project,
        context,
        gold,
        problem,
        execution_id="m4-descriptive",
        key="m4-descriptive-key",
    )
    request["module_input"].pop("target_column")
    request["module_input"]["model_policy"] = {
        "problem_type": "descriptive",
        "allowed_techniques": ["descriptive_statistics"],
    }
    response = client.post(
        f"/api/v1/projects/{project['id']}/executions/m4", json=request
    )
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "succeeded"
    _assert_m4_output_contract(result)
    assert result["module_output"]["candidates"][0]["technique"] == "descriptive_statistics"
