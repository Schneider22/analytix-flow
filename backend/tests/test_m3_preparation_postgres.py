from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Artifact, ArtifactLineage, Execution, Project
from app.m3_preparation import M3PreparationModule
from app.schemas import ArtifactCreate, ArtifactReferenceInput, ContextCreate, M3PreparationRequest
from app.services import create_artifact, create_context_snapshot
from app.storage import LocalArtifactStore
from tests.postgres_support import require_migrated_postgres


def _artifact_reference(artifact: Artifact) -> dict:
    return {
        "artifact_id": artifact.logical_id,
        "artifact_type": artifact.artifact_type,
        "artifact_version": artifact.artifact_version,
        "version_number": artifact.version_number,
        "version_id": artifact.id,
        "content_hash": artifact.content_hash,
        "layer": artifact.layer,
        "media_type": artifact.media_type,
    }


def test_m3_persists_project_scoped_lineage_in_postgresql():
    engine = require_migrated_postgres()
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    project_id = str(uuid4())
    execution_id = f"m3-pg-{uuid4().hex}"
    try:
        with factory() as db:
            project = Project(
                id=project_id,
                company_name="M3 PostgreSQL Test",
                company_description="Synthetic",
                business_need="Synthetic",
                expected_objective="Synthetic",
                business_rules=[],
                constraints=[],
                success_criteria=["Synthetic"],
            )
            db.add(project)
            db.commit()
            context = create_context_snapshot(
                db,
                project_id,
                ContextCreate(
                    context={
                        "company_name": "M3 PostgreSQL Test",
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
            artifact_root = Path("/tmp") / f"analytixflow-m3-pg-{uuid4().hex}"
            store = LocalArtifactStore(artifact_root, max_bytes=1024 * 1024)
            source_bytes = b"Order ID,Amount\n1,10\n1,10\n2,20\n"
            source_stored = store.put(source_bytes)
            source = create_artifact(
                db,
                project_id,
                ArtifactCreate(
                    artifact_id=f"source-{uuid4().hex}",
                    artifact_type="source",
                    artifact_version="v1",
                    content_hash=source_stored.content_hash,
                    storage_id=source_stored.storage_id,
                    media_type="text/csv",
                    layer="source",
                ),
                store,
                max_metadata_bytes=262144,
            )
            source_ref = _artifact_reference(source)
            manifest = {
                "execution_id": f"m2-source-{uuid4().hex}",
                "project_id": project_id,
                "module_id": "m2",
                "contract_version": "v1.0",
                "source_manifest": [
                    {
                        "source_artifact": source_ref,
                        "preserved": True,
                        "content_hash": source.content_hash,
                        "metadata": {"format": "csv", "delimiter": ",", "header_row": 0},
                    }
                ],
            }
            manifest_stored = store.put(json.dumps(manifest, sort_keys=True).encode("utf-8"))
            bronze = create_artifact(
                db,
                project_id,
                ArtifactCreate(
                    artifact_id=f"bronze-{uuid4().hex}",
                    artifact_type="dataset.bronze",
                    artifact_version="v1",
                    content_hash=manifest_stored.content_hash,
                    storage_id=manifest_stored.storage_id,
                    media_type="application/json",
                    layer="bronze",
                    produced_by_module="m2",
                    parent_artifact_refs=[
                        ArtifactReferenceInput(
                            artifact_id=source.logical_id,
                            artifact_version=source.artifact_version,
                        )
                    ],
                ),
                store,
                max_metadata_bytes=262144,
            )
            payload = M3PreparationRequest.model_validate(
                {
                    "project_id": project_id,
                    "execution_id": execution_id,
                    "module_id": "m3",
                    "contract_version": "v1.1",
                    "context_snapshot_id": context.id,
                    "status": "requested",
                    "correlation_id": f"corr-{execution_id}",
                    "idempotency_key": f"key-{execution_id}",
                    "module_input": {
                        "bronze_artifacts": [_artifact_reference(bronze)],
                        "transformation_plan": {
                            "rules": [
                                {
                                    "rule_id": "drop-duplicates",
                                    "action": "drop_duplicate_rows",
                                    "reason": "Keep one copy of repeated source rows.",
                                    "approval_required": False,
                                }
                            ]
                        },
                        "business_rules": [],
                        "quality_policy": {
                            "required_checks": ["non_empty_dataset", "no_duplicate_rows"],
                            "blocking_conditions": ["non_empty_dataset", "no_duplicate_rows"],
                        },
                    },
                }
            )
            result = M3PreparationModule().execute(
                db,
                project_id,
                payload,
                store,
                max_metadata_bytes=262144,
            )
            assert result["status"] == "succeeded"
            replay = M3PreparationModule().execute(
                db,
                project_id,
                payload,
                store,
                max_metadata_bytes=262144,
            )
            assert replay == result
            silver_id = result["module_output"]["silver_dataset"]["version_id"]
            gold_id = result["module_output"]["gold_dataset"]["version_id"]
            lineage = list(
                db.scalars(
                    select(ArtifactLineage).where(
                        ArtifactLineage.project_id == project_id,
                        ArtifactLineage.child_artifact_id.in_([silver_id, gold_id]),
                    )
                )
            )
            assert len(lineage) == 2
            execution = db.get(Execution, execution_id)
            assert execution is not None
            assert execution.status == "succeeded"
    finally:
        engine.dispose()
