from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models import Artifact, AuditEvent, Project, ProjectContextSnapshot
from app.db.session import build_engine


def make_session():
    engine = build_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine, Session(engine)


def test_immutable_records_and_artifacts_cannot_be_mutated():
    engine, db = make_session()
    try:
        project = Project(
            company_name="Synthetic",
            company_description="Synthetic",
            business_need="Synthetic",
            expected_objective="Synthetic",
            business_rules=[],
            constraints=[],
            success_criteria=["Synthetic"],
        )
        db.add(project)
        db.flush()
        snapshot = ProjectContextSnapshot(
            project_id=project.id,
            version=1,
            context_data={"value": "v1"},
            content_hash="sha256:" + "0" * 64,
            created_by="test",
        )
        audit = AuditEvent(
            project_id=project.id,
            actor_type="test",
            action="test",
            entity_type="project",
            entity_id=project.id,
            metadata_json={},
        )
        artifact = Artifact(
            project_id=project.id,
            logical_id="report",
            artifact_type="report",
            artifact_version="v1",
                version_number=1,
                legacy_version=False,
            content_hash="sha256:" + "1" * 64,
            parent_artifact_ids=[],
            metadata_json={},
        )
        db.add_all([snapshot, audit, artifact])
        db.commit()

        snapshot.context_data = {"value": "changed"}
        with pytest.raises(ValueError):
            db.commit()
        db.rollback()

        audit.metadata_json = {"changed": True}
        with pytest.raises(ValueError):
            db.commit()
        db.rollback()

        artifact.content_hash = "sha256:" + "2" * 64
        with pytest.raises(ValueError):
            db.commit()
        db.rollback()
    finally:
        db.close()
        engine.dispose()


def test_artifact_immutability_is_enforced_outside_the_orm():
    engine, db = make_session()
    try:
        project = Project(
            company_name="Synthetic",
            company_description="Synthetic",
            business_need="Synthetic",
            expected_objective="Synthetic",
            business_rules=[],
            constraints=[],
            success_criteria=["Synthetic"],
        )
        db.add(project)
        db.flush()
        artifact = Artifact(
            project_id=project.id,
            logical_id="report",
            artifact_type="report",
            artifact_version="v1",
            version_number=1,
            legacy_version=False,
            content_hash="sha256:" + "1" * 64,
            parent_artifact_ids=[],
            metadata_json={},
        )
        db.add(artifact)
        db.commit()

        with pytest.raises(IntegrityError):
            db.execute(
                text("UPDATE artifacts SET content_hash = :content_hash WHERE id = :id"),
                {"content_hash": "sha256:" + "2" * 64, "id": artifact.id},
            )
        db.rollback()
        with pytest.raises(IntegrityError):
            db.execute(text("DELETE FROM artifacts WHERE id = :id"), {"id": artifact.id})
        db.rollback()
    finally:
        db.close()
        engine.dispose()


def test_artifact_predecessor_fk_rejects_cross_identity_missing_and_cycle_shapes():
    engine, db = make_session()
    try:
        project_one = Project(
            company_name="One",
            company_description="Synthetic",
            business_need="Synthetic",
            expected_objective="Synthetic",
            business_rules=[],
            constraints=[],
            success_criteria=["Synthetic"],
        )
        project_two = Project(
            company_name="Two",
            company_description="Synthetic",
            business_need="Synthetic",
            expected_objective="Synthetic",
            business_rules=[],
            constraints=[],
            success_criteria=["Synthetic"],
        )
        db.add_all([project_one, project_two])
        db.flush()
        predecessor = Artifact(
            project_id=project_one.id,
            logical_id="report",
            artifact_type="report",
            artifact_version="v1",
            version_number=1,
            legacy_version=False,
            content_hash="sha256:" + "1" * 64,
            parent_artifact_ids=[],
            metadata_json={},
        )
        db.add(predecessor)
        db.flush()

        def assert_invalid(**values):
            candidate = Artifact(
                artifact_type="report",
                artifact_version="v2",
                version_number=2,
                legacy_version=False,
                content_hash="sha256:" + "2" * 64,
                parent_artifact_ids=[],
                metadata_json={},
                **values,
            )
            db.add(candidate)
            with pytest.raises(IntegrityError):
                db.flush()
            db.rollback()

        assert_invalid(
            project_id=project_two.id,
            logical_id="report",
            predecessor_artifact_id=predecessor.id,
            predecessor_version_number=1,
        )
        assert_invalid(
            project_id=project_one.id,
            logical_id="other-report",
            predecessor_artifact_id=predecessor.id,
            predecessor_version_number=1,
        )
        assert_invalid(
            project_id=project_one.id,
            logical_id="report",
            predecessor_artifact_id="missing-predecessor",
            predecessor_version_number=1,
        )
        assert_invalid(
            project_id=project_one.id,
            logical_id="report",
            predecessor_artifact_id=predecessor.id,
            predecessor_version_number=2,
        )
    finally:
        db.close()
        engine.dispose()
