from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from tempfile import TemporaryDirectory

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Artifact, Project, ProjectContextSnapshot
from app.schemas import ArtifactCreate, ContextCreate
from app.services import ConflictError, create_artifact, create_context_snapshot
from app.storage import LocalArtifactStore
from tests.postgres_support import (
    ALLOWED_CONCURRENCY_DATABASES,
    CONCURRENCY_DATABASE_URL_ENV,
    CONCURRENCY_EXPECTED_DATABASE_ENV,
    DEFAULT_CONCURRENCY_DATABASE,
    require_migrated_postgres,
)


def _require_concurrency_postgres():
    return require_migrated_postgres(
        database_url_env=CONCURRENCY_DATABASE_URL_ENV,
        expected_database_env=CONCURRENCY_EXPECTED_DATABASE_ENV,
        default_expected_database=DEFAULT_CONCURRENCY_DATABASE,
        allowed_databases=ALLOWED_CONCURRENCY_DATABASES,
    )


def test_concurrent_context_versions_are_unique():
    engine = _require_concurrency_postgres()
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
        # Service functions commit independently so worker transactions can
        # observe the same project. The project id is unique and rows are
        # intentionally retained in the isolated test database; no automatic
        # DELETE/TRUNCATE operation may bypass immutability guarantees.
        engine.dispose()


def test_concurrent_artifact_version_creation_is_unique_and_chained():
    engine = _require_concurrency_postgres()
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
        # See the isolation note in the context concurrency test above.
        engine.dispose()
