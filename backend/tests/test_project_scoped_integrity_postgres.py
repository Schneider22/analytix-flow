from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import delete, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from app.db.models import (
    Approval,
    Artifact,
    ArtifactLineage,
    AuditEvent,
    Decision,
    DecisionArtifactEvidence,
    Project,
    ProjectContextSnapshot,
)
from tests.postgres_support import require_migrated_postgres


@pytest.fixture(scope="module")
def postgres_engine():
    engine = require_migrated_postgres()
    yield engine
    engine.dispose()


@pytest.fixture()
def postgres_session(postgres_engine):
    connection = postgres_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, autoflush=False, expire_on_commit=False)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


def _project(label: str) -> Project:
    return Project(
        id=str(uuid4()),
        company_name=f"Project {label}",
        company_description="Synthetic PostgreSQL integrity test",
        business_need="Synthetic",
        expected_objective="Synthetic",
        business_rules=[],
        constraints=[],
        success_criteria=["Synthetic"],
    )


def _artifact(project_id: str, logical_id: str) -> Artifact:
    return Artifact(
        id=str(uuid4()),
        project_id=project_id,
        logical_id=logical_id,
        artifact_type="test",
        artifact_version="v1",
        version_number=1,
        legacy_version=False,
        content_hash=f"sha256:{uuid4().hex}{uuid4().hex}",
        parent_artifact_ids=[],
        metadata_json={},
    )


def _decision(project_id: str) -> Decision:
    return Decision(
        project_id=project_id,
        decision_type="integrity-test",
        question="Which synthetic option?",
        options=["a"],
        selected_option="a",
        rationale="Synthetic",
        status="decided",
        decided_by="test",
        evidence_artifact_ids=[],
    )


def _snapshot(project_id: str, version: int = 1, predecessor_id: str | None = None) -> ProjectContextSnapshot:
    return ProjectContextSnapshot(
        project_id=project_id,
        version=version,
        predecessor_id=predecessor_id,
        context_data={"version": version},
        content_hash="sha256:" + "0" * 64,
        created_by="test",
    )


def test_postgresql_rejects_cross_project_context_predecessor(postgres_session):
    project_a = _project("context-A")
    project_b = _project("context-B")
    predecessor = _snapshot(project_a.id)
    postgres_session.add_all([project_a, project_b, predecessor])
    postgres_session.flush()

    with postgres_session.begin_nested():
        postgres_session.add(_snapshot(project_b.id, predecessor_id=predecessor.id))
        with pytest.raises(IntegrityError):
            postgres_session.flush()


def test_postgresql_accepts_root_and_same_project_context_predecessor(postgres_session):
    project = _project("context-chain")
    root = _snapshot(project.id, version=1)
    postgres_session.add_all([project, root])
    postgres_session.flush()

    child = _snapshot(project.id, version=2, predecessor_id=root.id)
    postgres_session.add(child)
    postgres_session.flush()

    assert child.predecessor_id == root.id
    assert child.predecessor is root


def test_postgresql_rejects_direct_mutation_of_immutable_records(postgres_session):
    project = _project("immutable")
    snapshot = _snapshot(project.id)
    decision = _decision(project.id)
    approval = Approval(
        project_id=project.id,
        action="select_alternative",
        scope_type="project",
        status="pending",
        scope_hash="sha256:" + "0" * 64,
        requested_by="test",
    )
    audit_event = AuditEvent(
        project_id=project.id,
        actor_type="test",
        action="test.created",
        entity_type="test",
        entity_id=project.id,
        metadata_json={},
    )
    postgres_session.add_all([project, snapshot, decision, approval, audit_event])
    postgres_session.flush()

    mutations = (
        ("UPDATE project_context_snapshots SET created_by = 'changed' WHERE id = :id", {"id": snapshot.id}),
        ("UPDATE decisions SET rationale = 'changed' WHERE id = :id", {"id": decision.id}),
        ("UPDATE audit_events SET action = 'changed' WHERE id = :id", {"id": audit_event.id}),
        ("UPDATE approvals SET action = 'changed' WHERE id = :id", {"id": approval.id}),
        ("DELETE FROM approvals WHERE id = :id", {"id": approval.id}),
    )
    for statement, parameters in mutations:
        savepoint = postgres_session.begin_nested()
        try:
            with pytest.raises(DBAPIError):
                postgres_session.execute(text(statement), parameters)
        finally:
            savepoint.rollback()


def test_postgresql_rejects_cross_project_approval_lineage_and_evidence(
    postgres_session,
):
    project_a = _project("A")
    project_b = _project("B")
    artifact_a = _artifact(project_a.id, "a")
    artifact_b = _artifact(project_b.id, "b")
    decision_a = _decision(project_a.id)
    postgres_session.add_all([project_a, project_b, artifact_a, artifact_b, decision_a])
    postgres_session.flush()

    with postgres_session.begin_nested():
        postgres_session.add(
            Approval(
                project_id=project_a.id,
                action="approve_test_artifact",
                scope_type="artifact",
                status="pending",
                artifact_id=artifact_b.id,
                artifact_version="v1",
                scope_hash="sha256:" + "0" * 64,
                requested_by="test",
            )
        )
        with pytest.raises(IntegrityError):
            postgres_session.flush()

    with postgres_session.begin_nested():
        postgres_session.add(
            ArtifactLineage(
                project_id=project_a.id,
                child_artifact_id=artifact_a.id,
                parent_artifact_id=artifact_b.id,
            )
        )
        with pytest.raises(IntegrityError):
            postgres_session.flush()

    with postgres_session.begin_nested():
        postgres_session.add(
            DecisionArtifactEvidence(
                project_id=project_a.id,
                decision_id=decision_a.id,
                artifact_id=artifact_b.id,
            )
        )
        with pytest.raises(IntegrityError):
            postgres_session.flush()


def test_postgresql_accepts_same_project_relationships_and_retains_audit(
    postgres_session,
):
    project = _project("same")
    parent = _artifact(project.id, "parent")
    child = _artifact(project.id, "child")
    decision = _decision(project.id)
    postgres_session.add_all([project, parent, child, decision])
    postgres_session.flush()
    postgres_session.add_all(
        [
            ArtifactLineage(
                project_id=project.id,
                child_artifact_id=child.id,
                parent_artifact_id=parent.id,
            ),
            DecisionArtifactEvidence(
                project_id=project.id,
                decision_id=decision.id,
                artifact_id=parent.id,
            ),
            AuditEvent(
                project_id=project.id,
                actor_type="test",
                action="decision.created",
                entity_type="decision",
                entity_id=decision.id,
                metadata_json={},
            ),
        ]
    )
    postgres_session.flush()

    savepoint = postgres_session.begin_nested()
    try:
        with pytest.raises(DBAPIError):
            postgres_session.execute(delete(Decision).where(Decision.id == decision.id))
    finally:
        savepoint.rollback()

    assert postgres_session.scalar(
        select(DecisionArtifactEvidence).where(DecisionArtifactEvidence.decision_id == decision.id)
    ) is not None
    assert postgres_session.scalar(
        select(AuditEvent).where(AuditEvent.entity_id == decision.id)
    ) is not None
