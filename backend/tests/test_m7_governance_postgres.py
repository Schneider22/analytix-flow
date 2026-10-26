from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from tempfile import gettempdir
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.db.models import Approval, Artifact, ArtifactLineage, AuditEvent, Execution, Project
from app.m7_governance import M7GovernanceModule
from app.schemas import (
    ApprovalCreate,
    ArtifactCreate,
    ContextCreate,
    M7GovernanceRequest,
    M7ModuleInput,
    M7OperationalPolicy,
)
from app.services import ConflictError, NotFoundError, ValidationError, create_approval, create_artifact, create_context_snapshot
from app.storage import LocalArtifactStore
from tests.postgres_support import require_migrated_postgres
from tests.test_m7_governance import _assert_m7_output_contract


def _reference(artifact: Artifact) -> dict:
    return {
        "artifact_id": artifact.logical_id,
        "artifact_type": artifact.artifact_type,
        "artifact_version": artifact.artifact_version,
        "version_number": artifact.version_number,
        "version_id": artifact.id,
        "content_hash": artifact.content_hash,
        "layer": artifact.layer,
        "produced_by_module": artifact.produced_by_module,
    }


def test_m7_persists_project_scoped_audit_artifact_and_lineage_in_postgresql():
    engine = require_migrated_postgres()
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    project_id = str(uuid4())
    execution_m2_id = f"m2-pg-m7-{uuid4().hex}"
    m7_execution_id = f"m7-pg-{uuid4().hex}"
    store = LocalArtifactStore(
        Path(gettempdir()) / f"analytixflow-m7-pg-{uuid4().hex}",
        max_bytes=1024 * 1024,
    )
    try:
        with factory() as db:
            db.add(
                Project(
                    id=project_id,
                    company_name="M7 PostgreSQL Test",
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
                        "company_name": "M7 PostgreSQL Test",
                        "company_description": "Synthetic",
                        "business_need": "Synthetic",
                        "expected_objective": "Synthetic",
                        "business_rules": [],
                        "constraints": [],
                        "assumptions": [],
                        "success_criteria": ["Synthetic"],
                    },
                    created_by="m7-pg-test",
                ),
            )

            # Store an ingested Bronze dataset artifact
            stored_bronze = store.put(b"col_a,col_b\n10,20\n30,40\n")
            bronze = create_artifact(
                db,
                project_id,
                ArtifactCreate(
                    artifact_id=f"bronze-{uuid4().hex}",
                    artifact_type="dataset.bronze",
                    artifact_version="v1",
                    content_hash=stored_bronze.content_hash,
                    storage_id=stored_bronze.storage_id,
                    media_type="text/csv",
                    layer="bronze",
                    produced_by_module="m2",
                ),
                store,
                max_metadata_bytes=262144,
            )
            bronze_ref = _reference(bronze)

            # Add an execution for M2
            t0 = datetime(2026, 10, 24, 12, 0, 0, tzinfo=timezone.utc)
            t1 = datetime(2026, 10, 24, 12, 0, 10, tzinfo=timezone.utc)
            exec_m2 = Execution(
                id=execution_m2_id,
                project_id=project_id,
                module_id="m2",
                contract_version="v1.0",
                context_snapshot_id=context.id,
                status="succeeded",
                idempotency_key=f"key-{execution_m2_id}",
                correlation_id=f"corr-{execution_m2_id}",
                input_hash="sha256:" + "0" * 64,
                output_hash="sha256:" + "1" * 64,
                requested_at=t0,
                started_at=t0,
                completed_at=t1,
            )
            db.add(exec_m2)
            db.commit()

            # Execute M7
            payload = M7GovernanceRequest.model_validate(
                {
                    "project_id": project_id,
                    "execution_id": m7_execution_id,
                    "module_id": "m7",
                    "contract_version": "v1.0",
                    "context_snapshot_id": context.id,
                    "status": "requested",
                    "correlation_id": f"corr-{m7_execution_id}",
                    "idempotency_key": f"key-{m7_execution_id}",
                    "requested_by": "m7-pg-tester",
                    "module_input": {
                        "project_artifacts": [bronze_ref],
                        "execution_ids": [execution_m2_id],
                        "operational_policy": {
                            "audit_retention_required": True,
                            "quality_checks": ["schema_validation"],
                            "freshness_checks": ["max_age_30d"],
                        },
                    },
                }
            )

            module = M7GovernanceModule()
            result = module.execute(
                db, project_id, payload, store, max_metadata_bytes=262144
            )

            assert result["status"] == "succeeded"
            _assert_m7_output_contract(result)

            # Verify audit artifact record in PostgreSQL
            audit_ref = result["module_output"]["audit_artifact"]
            audit_record = db.get(Artifact, audit_ref["version_id"])
            assert audit_record is not None
            assert audit_record.project_id == project_id
            assert audit_record.artifact_type == "governance.audit"
            assert audit_record.layer == "audit"
            assert audit_record.produced_by_module == "m7"

            # Verify lineage in PostgreSQL
            links = list(
                db.scalars(
                    select(ArtifactLineage).where(
                        ArtifactLineage.project_id == project_id,
                        ArtifactLineage.child_artifact_id == audit_record.id,
                    )
                )
            )
            assert {link.parent_artifact_id for link in links} == {bronze.id}

            # Verify audit event records in PostgreSQL
            events = list(
                db.scalars(
                    select(AuditEvent).where(
                        AuditEvent.project_id == project_id,
                        AuditEvent.module_id == "m7",
                    )
                )
            )
            actions = {e.action for e in events}
            assert "execution.started" in actions
            assert "execution.succeeded" in actions

    finally:
        shutil.rmtree(store.root, ignore_errors=True)
        engine.dispose()


def test_m7_idempotency_and_conflict_handling_in_postgresql():
    engine = require_migrated_postgres()
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    project_id = str(uuid4())
    m7_execution_id = f"m7-pg-idem-{uuid4().hex}"
    store = LocalArtifactStore(
        Path(gettempdir()) / f"analytixflow-m7-idem-{uuid4().hex}",
        max_bytes=1024 * 1024,
    )
    try:
        with factory() as db:
            db.add(
                Project(
                    id=project_id,
                    company_name="M7 Idempotency Test",
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
                        "company_name": "M7 Idempotency Test",
                        "company_description": "Synthetic",
                        "business_need": "Synthetic",
                        "expected_objective": "Synthetic",
                        "business_rules": [],
                        "constraints": [],
                        "assumptions": [],
                        "success_criteria": ["Synthetic"],
                    },
                    created_by="m7-pg-idem",
                ),
            )

            payload = M7GovernanceRequest.model_validate(
                {
                    "project_id": project_id,
                    "execution_id": m7_execution_id,
                    "module_id": "m7",
                    "contract_version": "v1.0",
                    "context_snapshot_id": context.id,
                    "status": "requested",
                    "correlation_id": f"corr-{m7_execution_id}",
                    "idempotency_key": f"key-{m7_execution_id}",
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
            )

            module = M7GovernanceModule()
            first = module.execute(
                db, project_id, payload, store, max_metadata_bytes=262144
            )
            assert first["status"] == "succeeded"

            # Replay with same key and input
            replay = module.execute(
                db, project_id, payload, store, max_metadata_bytes=262144
            )
            assert replay == first

            # Conflict: same key with different execution_id
            conflicting = M7GovernanceRequest.model_validate(
                {
                    "project_id": project_id,
                    "execution_id": f"diff-{m7_execution_id}",
                    "module_id": "m7",
                    "contract_version": "v1.0",
                    "context_snapshot_id": context.id,
                    "status": "requested",
                    "correlation_id": f"corr-diff-{m7_execution_id}",
                    "idempotency_key": f"key-{m7_execution_id}",
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
            )
            with pytest.raises(ConflictError):
                module.execute(
                    db, project_id, conflicting, store, max_metadata_bytes=262144
                )

    finally:
        shutil.rmtree(store.root, ignore_errors=True)
        engine.dispose()


def test_m7_failure_terminal_recorded_in_postgresql_on_invalid_artifact():
    engine = require_migrated_postgres()
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    project_id = str(uuid4())
    m7_execution_id = f"m7-pg-fail-{uuid4().hex}"
    store = LocalArtifactStore(
        Path(gettempdir()) / f"analytixflow-m7-fail-{uuid4().hex}",
        max_bytes=1024 * 1024,
    )
    try:
        with factory() as db:
            db.add(
                Project(
                    id=project_id,
                    company_name="M7 Fail Test",
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
                        "company_name": "M7 Fail Test",
                        "company_description": "Synthetic",
                        "business_need": "Synthetic",
                        "expected_objective": "Synthetic",
                        "business_rules": [],
                        "constraints": [],
                        "assumptions": [],
                        "success_criteria": ["Synthetic"],
                    },
                    created_by="m7-pg-fail",
                ),
            )

            # Reference a non-existent artifact
            payload = M7GovernanceRequest.model_validate(
                {
                    "project_id": project_id,
                    "execution_id": m7_execution_id,
                    "module_id": "m7",
                    "contract_version": "v1.0",
                    "context_snapshot_id": context.id,
                    "status": "requested",
                    "correlation_id": f"corr-{m7_execution_id}",
                    "idempotency_key": f"key-{m7_execution_id}",
                    "module_input": {
                        "project_artifacts": [
                            {
                                "artifact_id": "ghost-artifact",
                                "artifact_type": "dataset.bronze",
                                "artifact_version": "v1",
                                "version_number": 1,
                                "content_hash": "sha256:" + "0" * 64,
                            }
                        ],
                        "execution_ids": [],
                        "operational_policy": {
                            "audit_retention_required": True,
                            "quality_checks": [],
                            "freshness_checks": [],
                        },
                    },
                }
            )

            module = M7GovernanceModule()
            with pytest.raises(NotFoundError, match="not found for project"):
                module.execute(
                    db, project_id, payload, store, max_metadata_bytes=262144
                )

            # Verify that execution was committed as failed_terminal
            failed_exec = db.get(Execution, m7_execution_id)
            assert failed_exec is not None
            assert failed_exec.status == "failed_terminal"
            assert "not found for project" in (failed_exec.error_summary or "")

    finally:
        shutil.rmtree(store.root, ignore_errors=True)
        engine.dispose()
