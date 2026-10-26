from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError
from referencing import Registry, Resource

from app.schemas import (
    ContractArtifactReference,
    M7GovernanceRequest,
    M7GovernanceResult,
    M7MaintenancePlan,
    M7ModuleInput,
    M7ModuleOutput,
    M7NextAction,
    M7OperationalIndicator,
    M7OperationalPolicy,
    M7ProjectState,
)


def _schemas():
    root = Path(__file__).parents[2] / "contracts"
    if not root.is_dir():
        root = Path(__file__).parents[1] / "contracts"
    schemas = {}
    for path in root.rglob("*.json"):
        schema = json.loads(path.read_text(encoding="utf-8"))
        schemas[schema["$id"]] = schema
    registry = Registry().with_resources(
        (uri, Resource.from_contents(schema)) for uri, schema in schemas.items()
    )
    return schemas, registry


def _sample_artifact_ref(
    artifact_id: str = "art-1",
    artifact_type: str = "report",
    version: str = "v1",
    version_number: int = 1,
    layer: str = "audit",
) -> ContractArtifactReference:
    return ContractArtifactReference(
        artifact_id=artifact_id,
        artifact_type=artifact_type,
        artifact_version=version,
        version_number=version_number,
        version_id="ver-1",
        content_hash="sha256:" + "a" * 64,
        layer=layer,
        produced_by_module="m7",
    )


def test_m7_operational_policy_validation():
    valid = M7OperationalPolicy(
        audit_retention_required=True,
        quality_checks=["missing_values", "type_integrity"],
        freshness_checks=["source_timestamp_within_30d"],
    )
    assert valid.audit_retention_required is True
    assert len(valid.quality_checks) == 2
    assert len(valid.freshness_checks) == 1

    with pytest.raises(ValidationError):
        M7OperationalPolicy.model_validate({"quality_checks": []})


def test_m7_module_input_validation():
    art = _sample_artifact_ref()
    valid = M7ModuleInput(
        project_artifacts=[art],
        execution_ids=["exec-m1-01", "exec-m2-01"],
        operational_policy=M7OperationalPolicy(
            audit_retention_required=True,
            quality_checks=["schema_check"],
            freshness_checks=["freshness_check"],
        ),
    )
    assert len(valid.project_artifacts) == 1
    assert valid.execution_ids == ["exec-m1-01", "exec-m2-01"]

    with pytest.raises(ValidationError, match="execution_ids must contain unique items"):
        M7ModuleInput(
            project_artifacts=[],
            execution_ids=["exec-dup", "exec-dup"],
            operational_policy=M7OperationalPolicy(
                audit_retention_required=False,
                quality_checks=[],
                freshness_checks=[],
            ),
        )

    with pytest.raises(ValidationError, match="execution_id items cannot be empty"):
        M7ModuleInput(
            project_artifacts=[],
            execution_ids=["   "],
            operational_policy=M7OperationalPolicy(
                audit_retention_required=False,
                quality_checks=[],
                freshness_checks=[],
            ),
        )


def test_m7_governance_request_validation():
    art = _sample_artifact_ref()
    payload = {
        "project_id": "proj-100",
        "execution_id": "exec-m7-001",
        "module_id": "m7",
        "contract_version": "v1.0",
        "context_snapshot_id": "ctx-001",
        "status": "requested",
        "correlation_id": "corr-001",
        "idempotency_key": "idem-key-001",
        "module_input": {
            "project_artifacts": [art.model_dump(mode="json")],
            "execution_ids": ["exec-m2-001"],
            "operational_policy": {
                "audit_retention_required": True,
                "quality_checks": ["integrity"],
                "freshness_checks": ["timestamp"],
            },
        },
    }
    req = M7GovernanceRequest.model_validate(payload)
    assert req.module_id == "m7"
    assert req.contract_version == "v1.0"
    assert req.status == "requested"

    bad_module = dict(payload)
    bad_module["module_id"] = "m6"
    with pytest.raises(ValidationError):
        M7GovernanceRequest.model_validate(bad_module)

    bad_status = dict(payload)
    bad_status["status"] = "unknown_status"
    with pytest.raises(ValidationError):
        M7GovernanceRequest.model_validate(bad_status)

    bad_hash = dict(payload)
    bad_hash["input_hash"] = "invalid_hash"
    with pytest.raises(ValidationError):
        M7GovernanceRequest.model_validate(bad_hash)


def test_m7_operational_indicator_classifications():
    for classification in ("measured", "estimated", "hypothesis", "documentary_evidence"):
        ind = M7OperationalIndicator(
            name="test_indicator",
            classification=classification,
            value_status="active",
        )
        assert ind.classification == classification

    cost_ind = M7OperationalIndicator(
        name="operational_cost",
        classification="documentary_evidence",
        value_status="not_applicable",
    )
    assert cost_ind.value_status == "not_applicable"

    with pytest.raises(ValidationError):
        M7OperationalIndicator(
            name="invalid_ind",
            classification="unsupported_classification",
            value_status="active",
        )


def test_m7_project_state_and_maintenance_plan():
    state = M7ProjectState(
        current_phase="governance_operations",
        module_statuses={"m1": "succeeded", "m2": "succeeded", "m7": "running"},
        blocked_reasons=[],
    )
    assert state.current_phase == "governance_operations"
    assert state.module_statuses["m1"] == "succeeded"

    with pytest.raises(ValidationError):
        M7ProjectState(current_phase="", module_statuses={}, blocked_reasons=[])

    plan = M7MaintenancePlan(
        procedures=["rollback_procedure_v1", "reprocessing_procedure_v1"],
        future_controls=["model_drift_monitoring", "latency_alerting"],
    )
    assert len(plan.procedures) == 2
    assert len(plan.future_controls) == 2


def test_m7_pydantic_models_strictly_match_json_schemas():
    schemas, registry = _schemas()
    input_validator = Draft202012Validator(
        schemas["https://analytixflow.local/contracts/m7/input.schema.json"],
        registry=registry,
    )
    output_validator = Draft202012Validator(
        schemas["https://analytixflow.local/contracts/m7/output.schema.json"],
        registry=registry,
    )

    art = _sample_artifact_ref()
    request_data = {
        "project_id": "proj-001",
        "execution_id": "exec-m7-01",
        "module_id": "m7",
        "contract_version": "v1.0",
        "context_snapshot_id": "ctx-001",
        "status": "requested",
        "correlation_id": "corr-m7-01",
        "idempotency_key": "key-m7-01",
        "artifact_refs": [],
        "approval_refs": [],
        "warnings": [],
        "errors": [],
        "requested_by": "m7-requester",
        "module_input": {
            "project_artifacts": [art.model_dump(mode="json")],
            "execution_ids": ["exec-m1", "exec-m2"],
            "operational_policy": {
                "audit_retention_required": True,
                "quality_checks": ["completeness", "validity"],
                "freshness_checks": ["max_age_hours_24"],
            },
        },
    }
    m7_request = M7GovernanceRequest.model_validate(request_data)
    input_validator.validate(m7_request.model_dump(mode="json", exclude_none=True))

    audit_art = _sample_artifact_ref(
        artifact_id="audit-log-m7",
        artifact_type="governance.audit",
        layer="audit",
    )
    result_data = {
        "project_id": "proj-001",
        "execution_id": "exec-m7-01",
        "module_id": "m7",
        "contract_version": "v1.0",
        "context_snapshot_id": "ctx-001",
        "correlation_id": "corr-m7-01",
        "status": "succeeded",
        "artifacts": [audit_art.model_dump(mode="json")],
        "approval_refs": [],
        "warnings": [],
        "errors": [],
        "next_actions": [
            {
                "action": "review_audit_log",
                "requires_approval": False,
                "target_module": "m8",
            }
        ],
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "output_hash": "sha256:" + "b" * 64,
        "module_output": {
            "audit_artifact": audit_art.model_dump(mode="json"),
            "project_state": {
                "current_phase": "governance_operations",
                "module_statuses": {"m1": "succeeded", "m7": "succeeded"},
                "blocked_reasons": [],
            },
            "operational_indicators": [
                {
                    "name": "mean_module_latency_seconds",
                    "classification": "measured",
                    "value_status": "42.5",
                },
                {
                    "name": "data_freshness_status",
                    "classification": "measured",
                    "value_status": "compliant",
                    "source_artifact": art.model_dump(mode="json"),
                },
                {
                    "name": "operational_cloud_cost",
                    "classification": "documentary_evidence",
                    "value_status": "not_applicable",
                },
            ],
            "maintenance_plan": {
                "procedures": [
                    "Retain immutable artifacts; rollback by resolving new approval without deleting history."
                ],
                "future_controls": [
                    "Deploy drift monitoring when continuous production serving is introduced."
                ],
            },
        },
    }
    m7_result = M7GovernanceResult.model_validate(result_data)
    output_validator.validate(m7_result.model_dump(mode="json", exclude_none=True))
