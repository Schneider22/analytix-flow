from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.db.models import Artifact, ArtifactLineage, Execution, Project
from app.m4_modeling import M4ModelingModule
from app.schemas import ArtifactCreate, ContextCreate, M4ModelingRequest
from app.services import create_artifact, create_context_snapshot
from app.storage import LocalArtifactStore
from tests.postgres_support import require_migrated_postgres


def _contract_ref(source: Artifact) -> dict:
    return {
        "artifact_id": source.logical_id,
        "artifact_type": source.artifact_type,
        "artifact_version": source.artifact_version,
        "version_number": source.version_number,
        "version_id": source.id,
        "predecessor_version_id": source.predecessor_artifact_id,
        "content_hash": source.content_hash,
        "media_type": source.media_type,
        "layer": source.layer,
        "produced_by_module": source.produced_by_module,
        "created_at": source.created_at,
    }


def test_m4_persists_candidates_and_lineage_in_postgresql():
    engine = require_migrated_postgres()
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    project_id = str(uuid4())
    execution_id = f"m4-pg-{uuid4().hex}"
    try:
        with factory() as db:
            db.add(
                Project(
                    id=project_id,
                    company_name="M4 PostgreSQL Test",
                    company_description="Synthetic",
                    business_need="Synthetic",
                    expected_objective="Synthetic",
                    business_rules=[],
                    constraints=[],
                    success_criteria=["Synthetic"],
                )
            )
            db.commit()
            context = create_context_snapshot(
                db,
                project_id,
                ContextCreate(
                    context={
                        "company_name": "M4 PostgreSQL Test",
                        "company_description": "Synthetic",
                        "business_need": "Synthetic",
                        "expected_objective": "Synthetic",
                        "business_rules": [],
                        "constraints": [],
                        "assumptions": [],
                        "success_criteria": ["Synthetic"],
                    },
                    created_by="test",
                ),
            )
            store = LocalArtifactStore(
                Path("/tmp") / f"analytixflow-m4-pg-{uuid4().hex}",
                max_bytes=1024 * 1024,
            )
            gold_stored = store.put(
                b"amount,region,label\n10,north,no\n11,north,no\n12,north,no\n13,north,no\n"
                b"20,south,yes\n21,south,yes\n22,south,yes\n23,south,yes\n"
            )
            gold = create_artifact(
                db,
                project_id,
                ArtifactCreate(
                    artifact_id=f"gold-{uuid4().hex}",
                    artifact_type="dataset.gold",
                    artifact_version="v1",
                    content_hash=gold_stored.content_hash,
                    storage_id=gold_stored.storage_id,
                    media_type="text/csv",
                    layer="gold",
                    produced_by_module="m3",
                ),
                store,
                max_metadata_bytes=262144,
            )
            problem_stored = store.put(b'{"problem_type":"classification","target":"label"}')
            problem = create_artifact(
                db,
                project_id,
                ArtifactCreate(
                    artifact_id=f"problem-{uuid4().hex}",
                    artifact_type="problem.definition",
                    artifact_version="v1",
                    content_hash=problem_stored.content_hash,
                    storage_id=problem_stored.storage_id,
                    media_type="application/json",
                    layer="other",
                    produced_by_module="m1",
                ),
                store,
                max_metadata_bytes=262144,
            )
            payload = M4ModelingRequest.model_validate(
                {
                    "project_id": project_id,
                    "execution_id": execution_id,
                    "module_id": "m4",
                    "contract_version": "v1.0",
                    "context_snapshot_id": context.id,
                    "status": "requested",
                    "correlation_id": f"corr-{execution_id}",
                    "idempotency_key": f"key-{execution_id}",
                    "module_input": {
                        "gold_dataset": _contract_ref(gold),
                        "problem_definition": _contract_ref(problem),
                        "target_column": "label",
                        "model_policy": {
                            "problem_type": "classification",
                            "allowed_techniques": ["logistic_regression"],
                        },
                        "split_policy": {"strategy": "holdout", "test_fraction": 0.25},
                        "reproducibility": {"random_seed": 23, "record_environment": True},
                    },
                }
            )
            result = M4ModelingModule().execute(
                db,
                project_id,
                payload,
                store,
                max_metadata_bytes=262144,
            )
            assert result["status"] == "succeeded"
            assert len(result["module_output"]["candidates"]) == 2
            replay = M4ModelingModule().execute(
                db,
                project_id,
                payload,
                store,
                max_metadata_bytes=262144,
            )
            assert replay == result
            lineage = list(
                db.scalars(
                    select(ArtifactLineage).where(ArtifactLineage.project_id == project_id)
                )
            )
            assert len(lineage) == 6
            assert all(link.project_id == project_id for link in lineage)
            execution = db.get(Execution, execution_id)
            assert execution is not None
            assert execution.status == "succeeded"
            assert db.scalar(
                select(Artifact).where(
                    Artifact.project_id == project_id,
                    Artifact.layer == "model",
                )
            ) is not None
    finally:
        engine.dispose()
