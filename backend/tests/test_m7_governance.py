from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from tests.test_api import context_payload, project_payload
from tests.test_m2_ingestion import _contract_ref, _m2_request


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


def _assert_m7_output_contract(result: dict) -> None:
    schemas, registry = _schemas()
    Draft202012Validator(
        schemas["https://analytixflow.local/contracts/m7/output.schema.json"],
        registry=registry,
    ).validate(result)


def _m7_request(
    project: dict,
    context: dict,
    artifacts: list[dict] | None = None,
    execution_ids: list[str] | None = None,
    *,
    execution_id: str = "m7-exec-1",
    key: str = "m7-key-1",
) -> dict:
    return {
        "project_id": project["id"],
        "execution_id": execution_id,
        "module_id": "m7",
        "contract_version": "v1.0",
        "context_snapshot_id": context["id"],
        "status": "requested",
        "correlation_id": f"corr-{execution_id}",
        "idempotency_key": key,
        "requested_by": "m7-auditor",
        "module_input": {
            "project_artifacts": [_contract_ref(a) for a in (artifacts or [])],
            "execution_ids": list(execution_ids or []),
            "operational_policy": {
                "audit_retention_required": True,
                "quality_checks": ["schema_validation", "null_check"],
                "freshness_checks": ["max_age_30d"],
            },
        },
    }


def test_m7_endpoint_executes_governance_and_validates_contract(client):
    project = client.post("/api/v1/projects", json=project_payload()).json()
    context = client.post(
        f"/api/v1/projects/{project['id']}/context", json=context_payload("m7-test")
    ).json()

    # Create and ingest a source dataset via M2
    source_content = b"id,amount,created_at\n1,10,2026-01-01\n2,20,2026-01-02\n"
    uploaded = client.post(
        f"/api/v1/projects/{project['id']}/artifacts/content",
        params={
            "artifact_type": "source",
            "artifact_version": "v1",
            "artifact_id": "orders-source",
            "media_type": "text/csv",
            "layer": "source",
        },
        content=source_content,
    ).json()

    m2_req = _m2_request(
        project,
        context,
        uploaded,
        execution_id="m2-exec-for-m7",
        key="m2-key-for-m7",
        fmt="csv",
    )
    m2_resp = client.post(f"/api/v1/projects/{project['id']}/executions/m2", json=m2_req)
    assert m2_resp.status_code == 200
    m2_result = m2_resp.json()
    bronze = m2_result["module_output"]["bronze_dataset"]

    # Execute M7 via API
    m7_payload = _m7_request(
        project,
        context,
        artifacts=[bronze],
        execution_ids=["m2-exec-for-m7"],
        execution_id="m7-exec-001",
        key="m7-key-001",
    )
    response = client.post(
        f"/api/v1/projects/{project['id']}/executions/m7",
        json=m7_payload,
    )
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "succeeded"
    _assert_m7_output_contract(result)

    # Validate module output components
    output = result["module_output"]
    audit_ref = output["audit_artifact"]
    assert audit_ref["artifact_type"] == "governance.audit"
    assert audit_ref["layer"] == "audit"
    assert audit_ref["produced_by_module"] == "m7"

    # Project state check
    state = output["project_state"]
    assert state["current_phase"] == "data_understanding"
    assert state["module_statuses"]["m2"] == "succeeded"
    assert state["module_statuses"]["m7"] == "succeeded"

    # Operational indicators check
    indicators = output["operational_indicators"]
    indicator_names = {ind["name"]: ind for ind in indicators}
    assert "execution_success_rate" in indicator_names
    assert indicator_names["execution_success_rate"]["classification"] == "measured"
    assert "mean_module_latency_seconds" in indicator_names
    assert "data_freshness_status" in indicator_names
    assert "operational_cloud_cost" in indicator_names
    assert indicator_names["operational_cloud_cost"]["classification"] == "documentary_evidence"
    assert indicator_names["operational_cloud_cost"]["value_status"] == "not_applicable"

    # Maintenance plan check
    plan = output["maintenance_plan"]
    assert len(plan["procedures"]) >= 1
    assert len(plan["future_controls"]) >= 1

    # Verify audit artifact content download via API
    content_resp = client.get(
        f"/api/v1/projects/{project['id']}/artifacts/{audit_ref['artifact_id']}/{audit_ref['artifact_version']}/content"
    )
    assert content_resp.status_code == 200
    assert content_resp.headers["X-Artifact-Content-Hash"] == audit_ref["content_hash"]
    audit_data = content_resp.json()
    assert audit_data["format"] == "analytixflow.m7.governance-audit.v1"
    assert audit_data["project_id"] == project["id"]
    assert audit_data["summary"]["executions_count"] >= 2


def test_m7_endpoint_idempotency_replay_and_conflict(client):
    project = client.post("/api/v1/projects", json=project_payload()).json()
    context = client.post(
        f"/api/v1/projects/{project['id']}/context", json=context_payload("m7-idem")
    ).json()

    req = _m7_request(project, context, execution_id="m7-idem-1", key="key-idem-unique")
    first_resp = client.post(f"/api/v1/projects/{project['id']}/executions/m7", json=req)
    assert first_resp.status_code == 200
    first_data = first_resp.json()

    # Replay with same key and same payload returns identical result
    replay_resp = client.post(f"/api/v1/projects/{project['id']}/executions/m7", json=req)
    assert replay_resp.status_code == 200
    assert replay_resp.json() == first_data

    # Reuse key with conflicting payload returns 409
    conflicting_req = _m7_request(
        project,
        context,
        execution_id="m7-idem-diff",
        key="key-idem-unique",
    )
    conflict_resp = client.post(
        f"/api/v1/projects/{project['id']}/executions/m7", json=conflicting_req
    )
    assert conflict_resp.status_code == 409


def test_m7_endpoint_detects_blocked_reasons_on_pending_approval(client):
    project = client.post("/api/v1/projects", json=project_payload()).json()
    context = client.post(
        f"/api/v1/projects/{project['id']}/context", json=context_payload("m7-block")
    ).json()

    # Create a pending approval
    app_resp = client.post(
        f"/api/v1/projects/{project['id']}/approvals",
        json={
            "action": "select_alternative",
            "scope_type": "project",
            "requested_by": "qa-reviewer",
            "reason": "Governance architecture review pending",
        },
    )
    assert app_resp.status_code == 201

    # Execute M7
    req = _m7_request(project, context, execution_id="m7-block-exec", key="m7-block-key")
    resp = client.post(f"/api/v1/projects/{project['id']}/executions/m7", json=req)
    assert resp.status_code == 200
    data = resp.json()
    blocked_reasons = data["module_output"]["project_state"]["blocked_reasons"]
    assert any("Pending approval required" in b for b in blocked_reasons)


def test_m7_endpoint_rejects_cross_project_artifacts(client):
    project_a = client.post("/api/v1/projects", json=project_payload()).json()
    context_a = client.post(
        f"/api/v1/projects/{project_a['id']}/context", json=context_payload("m7-cross-a")
    ).json()
    uploaded_a = client.post(
        f"/api/v1/projects/{project_a['id']}/artifacts/content",
        params={
            "artifact_type": "source",
            "artifact_version": "v1",
            "artifact_id": "source-a",
            "media_type": "text/csv",
            "layer": "source",
        },
        content=b"col1\n1\n",
    ).json()

    project_b = client.post("/api/v1/projects", json=project_payload()).json()
    context_b = client.post(
        f"/api/v1/projects/{project_b['id']}/context", json=context_payload("m7-cross-b")
    ).json()

    # Project B references Project A's artifact
    req_b = _m7_request(
        project_b,
        context_b,
        artifacts=[uploaded_a],
        execution_id="m7-cross-art-exec",
        key="m7-cross-art-key",
    )
    resp = client.post(f"/api/v1/projects/{project_b['id']}/executions/m7", json=req_b)
    assert resp.status_code == 404


def test_m7_endpoint_rejects_cross_project_executions(client):
    project_a = client.post("/api/v1/projects", json=project_payload()).json()
    context_a = client.post(
        f"/api/v1/projects/{project_a['id']}/context", json=context_payload("m7-cross-exec-a")
    ).json()
    uploaded_a = client.post(
        f"/api/v1/projects/{project_a['id']}/artifacts/content",
        params={
            "artifact_type": "source",
            "artifact_version": "v1",
            "artifact_id": "source-exec-a",
            "media_type": "text/csv",
            "layer": "source",
        },
        content=b"col1\n1\n",
    ).json()
    m2_a = client.post(
        f"/api/v1/projects/{project_a['id']}/executions/m2",
        json=_m2_request(
            project_a,
            context_a,
            uploaded_a,
            execution_id="m2-a-exec",
            key="m2-a-key",
            fmt="csv",
        ),
    ).json()

    project_b = client.post("/api/v1/projects", json=project_payload()).json()
    context_b = client.post(
        f"/api/v1/projects/{project_b['id']}/context", json=context_payload("m7-cross-exec-b")
    ).json()

    # Project B references Project A's execution
    req_b = _m7_request(
        project_b,
        context_b,
        execution_ids=["m2-a-exec"],
        execution_id="m7-cross-exec-b",
        key="m7-cross-exec-key",
    )
    resp = client.post(f"/api/v1/projects/{project_b['id']}/executions/m7", json=req_b)
    assert resp.status_code == 404


def test_m7_endpoint_requires_valid_context_snapshot(client):
    project = client.post("/api/v1/projects", json=project_payload()).json()
    req = {
        "project_id": project["id"],
        "execution_id": "m7-no-context",
        "module_id": "m7",
        "contract_version": "v1.0",
        "context_snapshot_id": "non-existent-snapshot-id",
        "status": "requested",
        "correlation_id": "corr-no-context",
        "idempotency_key": "key-no-context",
        "module_input": {
            "project_artifacts": [],
            "execution_ids": [],
            "operational_policy": {
                "audit_retention_required": True,
                "quality_checks": [],
                "freshness_checks": [],
            },
        },
    }
    resp = client.post(f"/api/v1/projects/{project['id']}/executions/m7", json=req)
    assert resp.status_code == 404
