from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from tests.test_api import context_payload, project_payload
from tests.test_m2_ingestion import _contract_ref, _m2_request


def _m3_request(project, context, bronze, *, execution_id: str, key: str):
    return {
        "project_id": project["id"],
        "execution_id": execution_id,
        "module_id": "m3",
        "contract_version": "v1.1",
        "context_snapshot_id": context["id"],
        "status": "requested",
        "correlation_id": f"corr-{execution_id}",
        "idempotency_key": key,
        "module_input": {
            "bronze_artifacts": [_contract_ref(bronze)],
            "transformation_plan": {
                "rules": [
                    {
                        "rule_id": "normalize-columns",
                        "action": "normalize_column_names",
                        "reason": "Use stable names for downstream consumers.",
                        "approval_required": False,
                    },
                    {
                        "rule_id": "remove-duplicates",
                        "action": "drop_duplicate_rows",
                        "reason": "Remove repeated source records after review.",
                        "approval_required": True,
                    },
                ]
            },
            "business_rules": ["Retain the source provenance."],
            "quality_policy": {
                "required_checks": ["non_empty_dataset", "columns_present", "no_duplicate_rows"],
                "blocking_conditions": ["non_empty_dataset", "columns_present"],
            },
        },
    }


def _assert_m3_output_contract(result: dict) -> None:
    contract_root = Path(__file__).parents[2] / "contracts"
    schemas = {}
    for path in contract_root.rglob("*.json"):
        schema = json.loads(path.read_text(encoding="utf-8"))
        schemas[schema["$id"]] = schema
    registry = Registry().with_resources(
        (uri, Resource.from_contents(schema)) for uri, schema in schemas.items()
    )
    output_schema = schemas["https://analytixflow.local/contracts/m3/output.schema.json"]
    Draft202012Validator(output_schema, registry=registry).validate(result)


def _create_m2_bronze(client, project, context):
    source = client.post(
        f"/api/v1/projects/{project['id']}/artifacts/content",
        params={
            "artifact_type": "source",
            "artifact_version": "v1",
            "artifact_id": "orders-source",
            "media_type": "text/csv",
            "layer": "source",
        },
        content=b"Order ID,Amount\n1,10\n1,10\n2,20\n",
    )
    assert source.status_code == 201
    m2 = client.post(
        f"/api/v1/projects/{project['id']}/executions/m2",
        json=_m2_request(
            project,
            context,
            source.json(),
            execution_id="m3-source-execution",
            key="m3-source-key",
            fmt="csv",
        ),
    )
    assert m2.status_code == 200
    return m2.json()["module_output"]["bronze_dataset"]


def test_m3_requires_approval_then_persists_silver_gold_and_is_idempotent(client):
    project = client.post("/api/v1/projects", json=project_payload()).json()
    context = client.post(
        f"/api/v1/projects/{project['id']}/context", json=context_payload("m3")
    ).json()
    bronze = _create_m2_bronze(client, project, context)
    request = _m3_request(
        project,
        context,
        bronze,
        execution_id="m3-execution-1",
        key="m3-key-1",
    )

    pending = client.post(
        f"/api/v1/projects/{project['id']}/executions/m3", json=request
    )
    assert pending.status_code == 200
    pending_result = pending.json()
    assert pending_result["status"] == "awaiting_approval"
    assert "silver_dataset" not in pending_result["module_output"]
    _assert_m3_output_contract(pending_result)

    approval_response = client.post(
        f"/api/v1/projects/{project['id']}/approvals",
        json={
            "action": "approve_transformations",
            "scope_type": "artifact",
            "artifact_id": bronze["artifact_id"],
            "artifact_version": bronze["artifact_version"],
            "requested_by": "test-user",
        },
    )
    assert approval_response.status_code == 201
    approval = approval_response.json()
    resolved = client.post(
        f"/api/v1/projects/{project['id']}/approvals/{approval['id']}/resolve",
        json={"status": "approved", "resolved_by": "test-user"},
    )
    assert resolved.status_code == 200
    resolved_approval = resolved.json()
    request["approval_refs"] = [
        {
            "approval_id": resolved_approval["id"],
            "action": resolved_approval["action"],
            "scope_type": resolved_approval["scope_type"],
            "status": resolved_approval["status"],
            "scope_hash": resolved_approval["scope_hash"],
            "artifact_id": bronze["artifact_id"],
            "artifact_version": bronze["artifact_version"],
            "approved_by": resolved_approval["resolved_by"],
            "approved_at": resolved_approval["resolved_at"],
        }
    ]

    result = client.post(
        f"/api/v1/projects/{project['id']}/executions/m3", json=request
    )
    assert result.status_code == 200
    result_data = result.json()
    assert result_data["status"] == "succeeded"
    _assert_m3_output_contract(result_data)
    assert result_data["module_output"]["silver_dataset"]["layer"] == "silver"
    assert result_data["module_output"]["gold_dataset"]["layer"] == "gold"
    assert len(result_data["module_output"]["lineage"]) == 2

    artifacts = client.get(f"/api/v1/projects/{project['id']}/artifacts").json()
    assert {item["layer"] for item in artifacts} == {"source", "bronze", "silver", "gold"}

    replay = client.post(
        f"/api/v1/projects/{project['id']}/executions/m3", json=request
    )
    assert replay.status_code == 200
    assert replay.json() == result_data


def test_m3_rejects_bronze_artifact_from_another_project(client):
    first = client.post("/api/v1/projects", json=project_payload()).json()
    second = client.post("/api/v1/projects", json=project_payload()).json()
    first_context = client.post(
        f"/api/v1/projects/{first['id']}/context", json=context_payload("first")
    ).json()
    second_context = client.post(
        f"/api/v1/projects/{second['id']}/context", json=context_payload("second")
    ).json()
    bronze = _create_m2_bronze(client, first, first_context)
    request = _m3_request(
        second,
        second_context,
        bronze,
        execution_id="m3-cross-project",
        key="m3-cross-project-key",
    )
    response = client.post(
        f"/api/v1/projects/{second['id']}/executions/m3", json=request
    )
    assert response.status_code == 404
