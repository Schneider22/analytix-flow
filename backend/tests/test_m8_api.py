from __future__ import annotations

import json
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.db.models import Artifact, ArtifactLineage, AuditEvent, Execution
from tests.test_api import context_payload, project_payload


def _setup_project_and_artifacts(client):
    app = client.app
    # 1. Create Project
    p_resp = client.post("/api/v1/projects", json=project_payload())
    assert p_resp.status_code == 201
    project_id = p_resp.json()["id"]

    # 2. Create Context Snapshot
    c_resp = client.post(f"/api/v1/projects/{project_id}/context", json=context_payload("v1"))
    assert c_resp.status_code == 201
    context_snapshot_id = c_resp.json()["id"]

    # 3. Create context artifact in store and DB
    ctx_bytes = json.dumps({"project_id": project_id, "scope": "test"}).encode("utf-8")
    stored_ctx = app.state.artifact_store.put(ctx_bytes)
    ctx_art_resp = client.post(
        f"/api/v1/projects/{project_id}/artifacts",
        json={
            "artifact_id": f"ctx-art-{uuid4().hex[:8]}",
            "artifact_type": "business_understanding",
            "artifact_version": "v1",
            "storage_id": stored_ctx.storage_id,
            "content_hash": stored_ctx.content_hash,
            "layer": "source",
            "produced_by_module": "m1",
        },
    )
    assert ctx_art_resp.status_code == 201
    ctx_art = ctx_art_resp.json()

    # 4. Create evaluation artifact in store and DB
    eval_bytes = json.dumps({
        "project_id": project_id,
        "metrics": {"accuracy": 0.935, "f1_score": 0.912},
    }).encode("utf-8")
    stored_eval = app.state.artifact_store.put(eval_bytes)
    eval_art_resp = client.post(
        f"/api/v1/projects/{project_id}/artifacts",
        json={
            "artifact_id": f"eval-art-{uuid4().hex[:8]}",
            "artifact_type": "report.evaluation",
            "artifact_version": "v1",
            "storage_id": stored_eval.storage_id,
            "content_hash": stored_eval.content_hash,
            "layer": "report",
            "produced_by_module": "m5",
        },
    )
    assert eval_art_resp.status_code == 201
    eval_art = eval_art_resp.json()

    return project_id, context_snapshot_id, ctx_art, eval_art


def _dashboard_request_payload(
    project_id: str,
    context_snapshot_id: str,
    ctx_art: dict,
    eval_art: dict,
    *,
    execution_id: str | None = None,
    idempotency_key: str | None = None,
    allow_hypotheses: bool = False,
) -> dict:
    return {
        "project_id": project_id,
        "execution_id": execution_id or f"exec-m8-{uuid4().hex[:8]}",
        "module_id": "m8",
        "contract_version": "v1.0",
        "context_snapshot_id": context_snapshot_id,
        "correlation_id": f"corr-{uuid4().hex[:8]}",
        "idempotency_key": idempotency_key or f"idem-{uuid4().hex[:8]}",
        "status": "requested",
        "requested_by": "api-tester",
        "module_input": {
            "context_artifacts": [
                {
                    "artifact_id": ctx_art["artifact_id"],
                    "artifact_type": ctx_art["artifact_type"],
                    "artifact_version": ctx_art["artifact_version"],
                    "version_number": ctx_art["version_number"] or 1,
                    "version_id": ctx_art["version_id"],
                    "content_hash": ctx_art["content_hash"],
                    "uri": ctx_art.get("uri"),
                    "layer": ctx_art["layer"],
                    "produced_by_module": ctx_art["produced_by_module"],
                }
            ],
            "result_artifacts": [
                {
                    "artifact_id": eval_art["artifact_id"],
                    "artifact_type": eval_art["artifact_type"],
                    "artifact_version": eval_art["artifact_version"],
                    "version_number": eval_art["version_number"] or 1,
                    "version_id": eval_art["version_id"],
                    "content_hash": eval_art["content_hash"],
                    "uri": eval_art.get("uri"),
                    "layer": eval_art["layer"],
                    "produced_by_module": eval_art["produced_by_module"],
                }
            ],
            "claim_policy": {
                "required_classification": True,
                "require_source_reference": True,
                "allow_hypotheses": allow_hypotheses,
            },
        },
    }


def test_create_and_get_dashboard_success(client):
    project_id, context_id, ctx_art, eval_art = _setup_project_and_artifacts(client)
    req_body = _dashboard_request_payload(project_id, context_id, ctx_art, eval_art)

    # 1. POST create dashboard
    resp = client.post(f"/api/v1/projects/{project_id}/dashboard", json=req_body)
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["project_id"] == project_id
    assert data["module_id"] == "m8"
    assert data["status"] == "succeeded"
    assert len(data["artifacts"]) == 1
    dashboard_art_ref = data["artifacts"][0]
    assert dashboard_art_ref["artifact_type"] == "dashboard.report"
    assert dashboard_art_ref["layer"] == "report"

    # Verify 6 sections present
    sections = data["module_output"]["sections"]
    assert len(sections) == 6
    section_ids = [s["section_id"] for s in sections]
    assert section_ids == [
        "business_diagnosis",
        "data_quality",
        "analytical_strategy",
        "evaluation_results",
        "impact_and_costs",
        "roadmap",
    ]

    # Verify roadmap present
    roadmap = data["module_output"]["roadmap"]
    assert len(roadmap) >= 1

    # 2. GET retrieve latest dashboard
    get_resp = client.get(f"/api/v1/projects/{project_id}/dashboard")
    assert get_resp.status_code == 200
    get_data = get_resp.json()
    assert get_data["execution_id"] == data["execution_id"]
    assert get_data["output_hash"] == data["output_hash"]

    # 3. Verify DB persistence and lineage
    with client.app.state.session_factory() as db:
        db_art = db.scalars(
            select(Artifact).where(
                Artifact.project_id == project_id,
                Artifact.artifact_type == "dashboard.report",
            )
        ).first()
        assert db_art is not None
        assert db_art.layer == "report"

        lineage_entries = list(
            db.scalars(
                select(ArtifactLineage).where(
                    ArtifactLineage.project_id == project_id,
                    ArtifactLineage.child_artifact_id == db_art.id,
                )
            )
        )
        assert len(lineage_entries) == 2  # ctx_art and eval_art


def test_dashboard_nonexistent_project(client):
    fake_pid = str(uuid4())
    req_body = {
        "project_id": fake_pid,
        "execution_id": f"exec-{uuid4().hex[:8]}",
        "module_id": "m8",
        "contract_version": "v1.0",
        "context_snapshot_id": f"ctx-{uuid4().hex[:8]}",
        "correlation_id": "corr-test",
        "idempotency_key": "idem-test",
        "status": "requested",
        "module_input": {
            "context_artifacts": [],
            "result_artifacts": [],
            "claim_policy": {
                "required_classification": True,
                "require_source_reference": True,
                "allow_hypotheses": False,
            },
        },
    }

    # POST returns 404
    post_resp = client.post(f"/api/v1/projects/{fake_pid}/dashboard", json=req_body)
    assert post_resp.status_code == 404

    # GET returns 404
    get_resp = client.get(f"/api/v1/projects/{fake_pid}/dashboard")
    assert get_resp.status_code == 404


def test_dashboard_alien_artifact_rejected(client):
    proj_a, ctx_a, ctx_art_a, eval_art_a = _setup_project_and_artifacts(client)
    proj_b, ctx_b, ctx_art_b, eval_art_b = _setup_project_and_artifacts(client)

    # Project A tries to reference Project B's artifact
    alien_req = _dashboard_request_payload(
        proj_a,
        ctx_a,
        ctx_art_a,
        eval_art_b,  # Alien artifact!
    )

    resp = client.post(f"/api/v1/projects/{proj_a}/dashboard", json=alien_req)
    assert resp.status_code in {404, 422}
    assert "not found for project" in resp.text.lower() or "isolation" in resp.text.lower()


def test_dashboard_incorrect_hash_rejected(client):
    proj, ctx, ctx_art, eval_art = _setup_project_and_artifacts(client)

    corrupted_art = dict(eval_art)
    corrupted_art["content_hash"] = "sha256:" + "f" * 64

    req = _dashboard_request_payload(proj, ctx, ctx_art, corrupted_art)
    resp = client.post(f"/api/v1/projects/{proj}/dashboard", json=req)
    assert resp.status_code == 422
    assert "content_hash" in resp.text.lower()


def test_dashboard_empty_evidence_rejected(client):
    proj, ctx, _, _ = _setup_project_and_artifacts(client)
    empty_req = {
        "project_id": proj,
        "execution_id": f"exec-{uuid4().hex[:8]}",
        "module_id": "m8",
        "contract_version": "v1.0",
        "context_snapshot_id": ctx,
        "correlation_id": "corr-test",
        "idempotency_key": "idem-test",
        "status": "requested",
        "module_input": {
            "context_artifacts": [],
            "result_artifacts": [],
            "claim_policy": {
                "required_classification": True,
                "require_source_reference": True,
                "allow_hypotheses": False,
            },
        },
    }
    resp = client.post(f"/api/v1/projects/{proj}/dashboard", json=empty_req)
    assert resp.status_code == 422
    assert "at least one" in resp.text.lower()


def test_dashboard_idempotency_replay_and_conflict(client):
    proj, ctx, ctx_art, eval_art = _setup_project_and_artifacts(client)
    exec_id = f"exec-{uuid4().hex[:8]}"
    idem_key = f"idem-{uuid4().hex[:8]}"

    req_body = _dashboard_request_payload(
        proj, ctx, ctx_art, eval_art, execution_id=exec_id, idempotency_key=idem_key
    )

    # 1. First execution
    resp1 = client.post(f"/api/v1/projects/{proj}/dashboard", json=req_body)
    assert resp1.status_code == 200
    res1_data = resp1.json()

    # 2. Replay with identical payload & idempotency key
    resp2 = client.post(f"/api/v1/projects/{proj}/dashboard", json=req_body)
    assert resp2.status_code == 200
    res2_data = resp2.json()
    assert res1_data["output_hash"] == res2_data["output_hash"]

    # Verify no duplicate executions were created
    with client.app.state.session_factory() as db:
        exec_count = len(
            list(
                db.scalars(
                    select(Execution).where(
                        Execution.project_id == proj,
                        Execution.idempotency_key == idem_key,
                    )
                )
            )
        )
        assert exec_count == 1

    # 3. Conflict: same idempotency key with different payload
    conflicting_req = dict(req_body)
    conflicting_req["module_input"]["claim_policy"]["allow_hypotheses"] = True
    resp_conflict = client.post(f"/api/v1/projects/{proj}/dashboard", json=conflicting_req)
    assert resp_conflict.status_code == 409


def test_get_dashboard_isolation(client):
    proj_a, ctx_a, ctx_art_a, eval_art_a = _setup_project_and_artifacts(client)
    proj_b, ctx_b, _, _ = _setup_project_and_artifacts(client)

    # Project A generates dashboard
    req_a = _dashboard_request_payload(proj_a, ctx_a, ctx_art_a, eval_art_a)
    client.post(f"/api/v1/projects/{proj_a}/dashboard", json=req_a)

    # Project B has not generated a dashboard -> must return 404
    resp_b = client.get(f"/api/v1/projects/{proj_b}/dashboard")
    assert resp_b.status_code == 404
