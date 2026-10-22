from __future__ import annotations

import os
from tempfile import TemporaryDirectory
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.db.models import Artifact, Project, ProjectContextSnapshot
from app.db.session import build_engine
from app.schemas import ArtifactCreate, ContextCreate
from app.services import ConflictError, create_artifact, create_context_snapshot
from app.storage import LocalArtifactStore


@pytest.mark.skipif(
    not os.getenv("ANALYTIXFLOW_TEST_DATABASE_URL"),
    reason="requires an explicitly isolated PostgreSQL test database",
)
def test_concurrent_context_versions_are_unique():
    database_url = os.environ["ANALYTIXFLOW_TEST_DATABASE_URL"]
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    try:
        with factory() as db:
            project = Project(
                company_name="Concurrency Test",
                company_description="Synthetic",
                business_need="Synthetic",
                expected_objective="Synthetic",
                business_rules=[],
                constraints=[],
                success_criteria=["Synthetic"],
            )
            db.add(project)
            db.commit()
            project_id = project.id

        def write_snapshot(label: str):
            with factory() as db:
                payload = ContextCreate(
                    context={
                        "company_name": "Concurrency Test",
                        "company_description": "Synthetic",
                        "business_need": "Synthetic",
                        "expected_objective": "Synthetic",
                        "business_rules": [],
                        "constraints": [],
                        "assumptions": [label],
                        "success_criteria": ["Synthetic"],
                    },
                    created_by="test",
                )
                create_context_snapshot(db, project_id, payload)

        with ThreadPoolExecutor(max_workers=2) as executor:
            list(executor.map(write_snapshot, ["a", "b"]))

        with factory() as db:
            versions = list(
                db.scalars(
                    select(ProjectContextSnapshot.version)
                    .where(ProjectContextSnapshot.project_id == project_id)
                    .order_by(ProjectContextSnapshot.version)
                )
            )
            assert versions == [1, 2]
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.mark.skipif(
    not os.getenv("ANALYTIXFLOW_TEST_DATABASE_URL"),
    reason="requires an explicitly isolated PostgreSQL test database",
)
def test_concurrent_artifact_version_creation_is_unique_and_chained():
    database_url = os.environ["ANALYTIXFLOW_TEST_DATABASE_URL"]
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    try:
        with factory() as db:
            project = Project(
                company_name="Artifact Concurrency Test",
                company_description="Synthetic",
                business_need="Synthetic",
                expected_objective="Synthetic",
                business_rules=[],
                constraints=[],
                success_criteria=["Synthetic"],
            )
            db.add(project)
            db.commit()
            project_id = project.id

        with TemporaryDirectory(prefix="analytixflow-artifacts-") as artifact_root:
            store = LocalArtifactStore(artifact_root, max_bytes=1024)

            def write_version(label: str):
                stored = store.put(label.encode("utf-8"))
                payload = ArtifactCreate(
                    artifact_id="concurrent-report",
                    artifact_type="report",
                    artifact_version="v1",
                    storage_id=stored.storage_id,
                    content_hash=stored.content_hash,
                )
                try:
                    with factory() as db:
                        create_artifact(
                            db,
                            project_id,
                            payload,
                            store,
                            max_metadata_bytes=262144,
                        )
                    return "created"
                except ConflictError:
                    return "conflict"

            with ThreadPoolExecutor(max_workers=2) as executor:
                outcomes = list(executor.map(write_version, ["one", "two"]))

            assert sorted(outcomes) == ["conflict", "created"]

        with factory() as db:
            rows = list(
                db.scalars(
                    select(Artifact)
                    .where(
                        Artifact.project_id == project_id,
                        Artifact.logical_id == "concurrent-report",
                    )
                )
            )
            assert len(rows) == 1
            assert rows[0].version_number == 1
            assert rows[0].predecessor_artifact_id is None
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()
