from __future__ import annotations

import hashlib

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import select

from app.api import get_db
from app.db.models import Artifact, ArtifactLineage


def project_payload():
    return {
        "company_name": "Example Analytics",
        "company_description": "Synthetic test organization.",
        "business_need": "Understand a recurring operational issue.",
        "expected_objective": "Support a measurable business decision.",
        "business_rules": ["Do not expose customer identifiers."],
        "constraints": ["Local execution only."],
        "success_criteria": ["Provide traceable evidence."],
        "owner_id": "test-owner",
    }


def context_payload(version_label: str):
    return {
        "context": {
            "company_name": "Example Analytics",
            "company_description": f"Synthetic context {version_label}.",
            "business_need": "Understand a recurring operational issue.",
            "expected_objective": "Support a measurable business decision.",
            "business_rules": ["Do not expose customer identifiers."],
            "constraints": ["Local execution only."],
            "assumptions": [version_label],
            "success_criteria": ["Provide traceable evidence."],
        },
        "created_by": "test-owner",
    }


def create_project(client):
    response = client.post("/api/v1/projects", json=project_payload())
    assert response.status_code == 201
    return response.json()


def artifact_payload(app, artifact_id=None, version="v1"):
    stored = app.state.artifact_store.put(b"synthetic-artifact")
    return {
        "artifact_id": artifact_id,
        "artifact_type": "test_report",
        "artifact_version": version,
        "storage_id": stored.storage_id,
        "content_hash": stored.content_hash,
        "layer": "report",
        "produced_by_module": "system",
        "metadata": {"note": "synthetic test artifact", "api_token": "must-not-persist"},
    }


def test_create_get_and_list_project(client):
    project = create_project(client)
    assert client.get(f"/api/v1/projects/{project['id']}").status_code == 200
    listed = client.get("/api/v1/projects").json()
    assert [item["id"] for item in listed] == [project["id"]]


def test_project_archiving_filters_audit_and_restore(client):
    project = create_project(client)
    project_id = project["id"]

    archived = client.post(
        f"/api/v1/projects/{project_id}/archive",
        headers={"X-Correlation-ID": "archive-correlation-001"},
        json={"actor_id": "operator", "reason": "Synthetic lifecycle test"},
    )
    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"
    assert archived.json()["archived_at"] is not None
    assert archived.json()["archived_from_status"] == "draft"

    assert client.get("/api/v1/projects").json() == []
    assert [item["id"] for item in client.get("/api/v1/projects", params={"archived": "only"}).json()] == [project_id]
    assert [item["id"] for item in client.get("/api/v1/projects", params={"archived": "include"}).json()] == [project_id]

    archive_audit = client.get(f"/api/v1/projects/{project_id}/audit").json()
    archive_event = next(item for item in archive_audit if item["action"] == "project.archived")
    assert archive_event["actor_id"] == "operator"
    assert archive_event["correlation_id"] == "archive-correlation-001"
    assert archive_event["metadata"]["previous_status"] == "draft"

    repeated_archive = client.post(
        f"/api/v1/projects/{project_id}/archive",
        json={"actor_id": "operator", "reason": "Must be rejected"},
    )
    assert repeated_archive.status_code == 409
    assert len([item for item in client.get(f"/api/v1/projects/{project_id}/audit").json() if item["action"] == "project.archived"]) == 1

    restored = client.post(
        f"/api/v1/projects/{project_id}/restore",
        json={"actor_id": "operator", "reason": "Synthetic restore test"},
    )
    assert restored.status_code == 200
    assert restored.json()["status"] == "draft"
    assert restored.json()["archived_at"] is None
    assert restored.json()["archived_from_status"] is None
    assert [item["id"] for item in client.get("/api/v1/projects").json()] == [project_id]
    assert any(item["action"] == "project.restored" for item in client.get(f"/api/v1/projects/{project_id}/audit").json())

    repeated_restore = client.post(
        f"/api/v1/projects/{project_id}/restore",
        json={"actor_id": "operator"},
    )
    assert repeated_restore.status_code == 409


def test_archived_project_preserves_history_and_blocks_mutations(client):
    project = create_project(client)
    project_id = project["id"]
    context = client.post(f"/api/v1/projects/{project_id}/context", json=context_payload("before-archive"))
    assert context.status_code == 201
    decision = client.post(
        f"/api/v1/projects/{project_id}/decisions",
        json={
            "decision_type": "select_alternative",
            "question": "Which alternative should proceed?",
            "options": ["alternative-a", "alternative-b"],
            "status": "pending",
        },
    )
    assert decision.status_code == 201
    artifact = client.post(
        f"/api/v1/projects/{project_id}/artifacts", json=artifact_payload(client.app, artifact_id="history", version="v1")
    )
    assert artifact.status_code == 201
    approval = client.post(
        f"/api/v1/projects/{project_id}/approvals",
        json={"action": "select_alternative", "requested_by": "operator"},
    )
    assert approval.status_code == 201

    archived = client.post(
        f"/api/v1/projects/{project_id}/archive",
        json={"actor_id": "operator", "reason": "Protect history"},
    )
    assert archived.status_code == 200

    assert len(client.get(f"/api/v1/projects/{project_id}/context").json()) == 1
    assert len(client.get(f"/api/v1/projects/{project_id}/decisions").json()) == 1
    assert len(client.get(f"/api/v1/projects/{project_id}/artifacts").json()) == 1
    assert len(client.get(f"/api/v1/projects/{project_id}/approvals").json()) == 1
    assert len(client.get(f"/api/v1/projects/{project_id}/audit").json()) >= 5

    blocked_context = client.post(f"/api/v1/projects/{project_id}/context", json=context_payload("blocked"))
    blocked_decision = client.post(
        f"/api/v1/projects/{project_id}/decisions",
        json={"decision_type": "test", "question": "Blocked?", "options": ["yes"]},
    )
    blocked_artifact = client.post(
        f"/api/v1/projects/{project_id}/artifacts", json=artifact_payload(client.app, artifact_id="blocked", version="v1")
    )
    blocked_content = client.post(
        f"/api/v1/projects/{project_id}/artifacts/content?artifact_type=source&artifact_version=v1&artifact_id=blocked-content",
        content=b"blocked",
    )
    blocked_approval = client.post(
        f"/api/v1/projects/{project_id}/approvals",
        json={"action": "select_alternative", "requested_by": "operator"},
    )
    assert [response.status_code for response in (blocked_context, blocked_decision, blocked_artifact, blocked_content, blocked_approval)] == [409, 409, 409, 409, 409]


def test_context_versions_are_append_only(client):
    project = create_project(client)
    first = client.post(f"/api/v1/projects/{project['id']}/context", json=context_payload("v1"))
    second = client.post(f"/api/v1/projects/{project['id']}/context", json=context_payload("v2"))
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["version"] == 1
    assert second.json()["version"] == 2
    assert second.json()["predecessor_id"] == first.json()["id"]
    history = client.get(f"/api/v1/projects/{project['id']}/context").json()
    assert [snapshot["version"] for snapshot in history] == [1, 2]
    assert history[0]["content_hash"] != history[1]["content_hash"]


def test_artifact_and_decision_are_related(client):
    project = create_project(client)
    artifact = client.post(
        f"/api/v1/projects/{project['id']}/artifacts", json=artifact_payload(client.app)
    )
    assert artifact.status_code == 201
    artifact_data = artifact.json()
    artifact_id = artifact_data["artifact_id"]
    assert artifact_data["metadata"]["api_token"] == "[REDACTED]"
    decision = client.post(
        f"/api/v1/projects/{project['id']}/decisions",
        json={
            "decision_type": "select_alternative",
            "question": "Which alternative should proceed?",
            "options": ["alternative-a", "alternative-b"],
            "selected_option": "alternative-a",
            "rationale": "Synthetic test rationale.",
            "evidence_artifact_refs": [{"artifact_id": artifact_id, "artifact_version": "v1"}],
            "status": "decided",
            "decided_by": "reviewer",
        },
    )
    assert decision.status_code == 201
    assert decision.json()["evidence_artifact_ids"] == [artifact_id]
    assert decision.json()["evidence_artifact_refs"] == [
        {"artifact_id": artifact_id, "artifact_version": "v1"}
    ]


def test_artifact_versions_have_logical_identity_and_are_unique(client):
    project = create_project(client)
    first = client.post(
        f"/api/v1/projects/{project['id']}/artifacts",
        json=artifact_payload(client.app, artifact_id="profile-report", version="v1"),
    )
    second = client.post(
        f"/api/v1/projects/{project['id']}/artifacts",
        json=artifact_payload(client.app, artifact_id="profile-report", version="v2"),
    )
    third = client.post(
        f"/api/v1/projects/{project['id']}/artifacts",
        json=artifact_payload(client.app, artifact_id="profile-report", version="v3"),
    )
    duplicate = client.post(
        f"/api/v1/projects/{project['id']}/artifacts",
        json=artifact_payload(client.app, artifact_id="profile-report", version="v1"),
    )
    assert first.status_code == 201
    assert second.status_code == 201
    assert third.status_code == 201
    assert first.json()["artifact_id"] == second.json()["artifact_id"] == third.json()["artifact_id"] == "profile-report"
    assert first.json()["version_id"] != second.json()["version_id"]
    assert first.json()["version_number"] == 1
    assert first.json()["predecessor_version_id"] is None
    assert second.json()["version_number"] == 2
    assert second.json()["predecessor_version_id"] == first.json()["version_id"]
    assert second.json()["predecessor_artifact_id"] == "profile-report"
    assert third.json()["version_number"] == 3
    assert third.json()["predecessor_version_id"] == second.json()["version_id"]
    assert duplicate.status_code == 409


def test_artifact_version_chain_rejects_gaps_and_wrong_same_identity_parent(client):
    project = create_project(client)
    first = client.post(
        f"/api/v1/projects/{project['id']}/artifacts",
        json=artifact_payload(client.app, artifact_id="profile-report", version="v1"),
    )
    assert first.status_code == 201

    first_version = client.post(
        f"/api/v1/projects/{project['id']}/artifacts",
        json={
            **artifact_payload(client.app, artifact_id="profile-report", version="v3"),
            "parent_artifact_refs": [{"artifact_id": "profile-report", "artifact_version": "v1"}],
        },
    )
    assert first_version.status_code == 409

    second = client.post(
        f"/api/v1/projects/{project['id']}/artifacts",
        json=artifact_payload(client.app, artifact_id="profile-report", version="v2"),
    )
    assert second.status_code == 201
    wrong_parent = client.post(
        f"/api/v1/projects/{project['id']}/artifacts",
        json={
            **artifact_payload(client.app, artifact_id="profile-report", version="v3"),
            "parent_artifact_refs": [{"artifact_id": "profile-report", "artifact_version": "v1"}],
        },
    )
    assert wrong_parent.status_code == 422
    client_supplied_predecessor = client.post(
        f"/api/v1/projects/{project['id']}/artifacts",
        json={
            **artifact_payload(client.app, artifact_id="profile-report", version="v3"),
            "parent_artifact_refs": [{"artifact_id": "profile-report", "artifact_version": "v2"}],
        },
    )
    assert client_supplied_predecessor.status_code == 422


def test_first_artifact_version_must_be_v1(client):
    project = create_project(client)
    response = client.post(
        f"/api/v1/projects/{project['id']}/artifacts",
        json=artifact_payload(client.app, artifact_id="profile-report", version="v2"),
    )
    assert response.status_code == 422


def test_historical_legacy_artifacts_remain_readable_without_invented_version(client):
    project = create_project(client)
    with client.app.state.session_factory() as db:
        db.add(
            Artifact(
                project_id=project["id"],
                logical_id="historical-report",
                artifact_type="report",
                artifact_version="historical-label",
                legacy_version=True,
                version_number=None,
                predecessor_artifact_id=None,
                predecessor_version_number=None,
                content_hash="sha256:" + "a" * 64,
                parent_artifact_ids=[],
                metadata_json={"source": "pre-chain"},
            )
        )
        db.commit()

    response = client.get(f"/api/v1/projects/{project['id']}/artifacts")
    assert response.status_code == 200
    historical = response.json()[0]
    assert historical["artifact_id"] == "historical-report"
    assert historical["legacy_version"] is True
    assert historical["version_number"] is None
    assert historical["predecessor_version_id"] is None


def test_artifact_content_endpoint_hashes_bytes_on_server(client):
    project = create_project(client)
    content = b"server-hashed-artifact"
    response = client.post(
        f"/api/v1/projects/{project['id']}/artifacts/content",
        params={"artifact_type": "source", "artifact_version": "v1", "artifact_id": "source-file"},
        content=content,
        headers={"content-type": "application/octet-stream"},
    )
    assert response.status_code == 201
    assert response.json()["content_hash"] == f"sha256:{hashlib.sha256(content).hexdigest()}"
    assert response.json()["uri"].startswith("local-artifact://")


def test_artifact_lineage_uses_explicit_foreign_keys(client):
    project = create_project(client)
    parent = client.post(
        f"/api/v1/projects/{project['id']}/artifacts",
        json=artifact_payload(client.app, artifact_id="source", version="v1"),
    ).json()
    child = client.post(
        f"/api/v1/projects/{project['id']}/artifacts",
        json={
            **artifact_payload(client.app, artifact_id="profile", version="v1"),
            "parent_artifact_refs": [{"artifact_id": "source", "artifact_version": "v1"}],
        },
    )
    assert child.status_code == 201
    with client.app.state.session_factory() as db:
        lineage = db.scalar(select(ArtifactLineage))
        assert lineage.child_artifact_id == child.json()["version_id"]
        assert lineage.parent_artifact_id == parent["version_id"]


def test_approval_resolve_cannot_be_reused(client):
    project = create_project(client)
    artifact = client.post(
        f"/api/v1/projects/{project['id']}/artifacts", json=artifact_payload(client.app)
    ).json()
    approval = client.post(
        f"/api/v1/projects/{project['id']}/approvals",
        json={
            "action": "approve_test_artifact",
            "artifact_id": artifact["artifact_id"],
            "artifact_version": "v1",
            "execution_id": "test-execution-1",
            "requested_by": "operator",
        },
    )
    assert approval.status_code == 201
    assert approval.json()["scope_hash"].startswith("sha256:")
    approval_id = approval.json()["id"]
    resolved = client.post(
        f"/api/v1/projects/{project['id']}/approvals/{approval_id}/resolve",
        json={"status": "approved", "resolved_by": "reviewer"},
    )
    assert resolved.status_code == 200
    reused = client.post(
        f"/api/v1/projects/{project['id']}/approvals/{approval_id}/resolve",
        json={"status": "rejected", "resolved_by": "reviewer"},
    )
    assert reused.status_code == 409


def test_approval_scope_is_server_calculated(client):
    project = create_project(client)
    response = client.post(
        f"/api/v1/projects/{project['id']}/approvals",
        json={
            "action": "select_alternative",
            "scope_type": "project",
            "scope_hash": "sha256:" + "0" * 64,
            "requested_by": "reviewer",
        },
    )
    assert response.status_code == 422


def test_audit_history_and_secret_redaction(client):
    project = create_project(client)
    artifact = client.post(
        f"/api/v1/projects/{project['id']}/artifacts", json=artifact_payload(client.app)
    )
    assert artifact.status_code == 201
    audit = client.get(f"/api/v1/projects/{project['id']}/audit")
    assert audit.status_code == 200
    payload = audit.json()
    assert any(item["action"] == "project.created" for item in payload)
    assert all("must-not-persist" not in str(item) for item in payload)


def test_correlation_id_is_propagated_to_audit(client):
    correlation_id = "audit-correlation-001"
    response = client.post(
        "/api/v1/projects",
        headers={"X-Correlation-ID": correlation_id},
        json=project_payload(),
    )
    assert response.status_code == 201
    assert response.headers["X-Correlation-ID"] == correlation_id
    audit_events = client.get(f"/api/v1/projects/{response.json()['id']}/audit").json()
    assert audit_events[0]["correlation_id"] == correlation_id


def test_validation_and_unknown_identifiers(client):
    invalid = client.post("/api/v1/projects", json={"company_name": "incomplete"})
    assert invalid.status_code == 422
    missing = client.get("/api/v1/projects/not-a-project")
    assert missing.status_code == 404
    missing_context = client.get("/api/v1/projects/not-a-project/context")
    assert missing_context.status_code == 404


def test_missing_foreign_artifact_is_rejected(client):
    project = create_project(client)
    response = client.post(
        f"/api/v1/projects/{project['id']}/decisions",
        json={
            "decision_type": "test",
            "question": "Question",
            "options": ["a"],
            "evidence_artifact_refs": [{"artifact_id": "missing-artifact", "artifact_version": "v1"}],
        },
    )
    assert response.status_code == 404


def test_missing_parent_artifact_is_rejected(client):
    project = create_project(client)
    response = client.post(
        f"/api/v1/projects/{project['id']}/artifacts",
        json={**artifact_payload(client.app), "parent_artifact_ids": ["missing-parent"]},
    )
    assert response.status_code == 404


def test_persistence_failure_returns_safe_error(client, app):
    class BrokenSession:
        def add(self, _value):
            return None

        def flush(self):
            raise SQLAlchemyError("simulated database failure")

        def close(self):
            return None

    def broken_db():
        yield BrokenSession()

    app.dependency_overrides[get_db] = broken_db
    try:
        response = client.post("/api/v1/projects", json=project_payload())
    finally:
        app.dependency_overrides.pop(get_db, None)
    assert response.status_code == 503
    assert response.json() == {"detail": "Persistence service unavailable"}


def test_health_endpoint(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}
