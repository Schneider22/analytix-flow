from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import gettempdir
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.db.models import Artifact, ArtifactLineage, AuditEvent, Execution, Project
from app.orchestrator import ProjectOrchestrator
from app.schemas import (
    ArtifactCreate,
    ClaimPolicy,
    ContextCreate,
    M8DashboardInput,
    M8ModuleInput,
)
from app.services import (
    ConflictError,
    NotFoundError,
    ValidationError,
    create_artifact,
    create_context_snapshot,
)
from app.storage import LocalArtifactStore
from tests.postgres_support import require_migrated_postgres


def _reference(artifact: Artifact) -> dict:
    return {
        "artifact_id": artifact.logical_id,
        "artifact_type": artifact.artifact_type,
        "artifact_version": artifact.artifact_version,
        "version_number": artifact.version_number,
        "version_id": artifact.id,
        "content_hash": artifact.content_hash,
        "uri": artifact.uri,
        "layer": artifact.layer,
        "produced_by_module": artifact.produced_by_module,
    }


def _setup_pg_project(db, store, project_name="M8 PostgreSQL Test"):
    project_id = str(uuid4())
    db.add(
        Project(
            id=project_id,
            company_name=project_name,
            company_description="Synthetic M8 testing",
            business_need="Executive dashboard assurance",
            expected_objective="Consolidated reporting and governance",
            business_rules=[],
            constraints=[],
            success_criteria=["Complete auditability"],
        )
    )
    db.commit()

    context = create_context_snapshot(
        db,
        project_id,
        ContextCreate(
            context={
                "company_name": project_name,
                "company_description": "Synthetic M8 testing",
                "business_need": "Executive dashboard assurance",
                "expected_objective": "Consolidated reporting and governance",
                "business_rules": [],
                "constraints": [],
                "assumptions": [],
                "success_criteria": ["Complete auditability"],
            },
            created_by="m8-pg-test",
        ),
    )

    # 1. Context source artifact
    ctx_payload = json.dumps({"project_id": project_id, "scope": "m8-pg-scope"}).encode("utf-8")
    stored_ctx = store.put(ctx_payload)
    ctx_art = create_artifact(
        db,
        project_id,
        ArtifactCreate(
            artifact_id=f"ctx-{uuid4().hex[:8]}",
            artifact_type="business_understanding",
            artifact_version="v1",
            content_hash=stored_ctx.content_hash,
            storage_id=stored_ctx.storage_id,
            uri=stored_ctx.uri,
            media_type="application/json",
            layer="source",
            produced_by_module="m1",
        ),
        store,
        max_metadata_bytes=65536,
    )

    # 2. Evaluation report artifact
    eval_payload = json.dumps({
        "project_id": project_id,
        "metrics": {"accuracy": 0.945, "f1_score": 0.923},
    }).encode("utf-8")
    stored_eval = store.put(eval_payload)
    eval_art = create_artifact(
        db,
        project_id,
        ArtifactCreate(
            artifact_id=f"eval-{uuid4().hex[:8]}",
            artifact_type="report.evaluation",
            artifact_version="v1",
            content_hash=stored_eval.content_hash,
            storage_id=stored_eval.storage_id,
            uri=stored_eval.uri,
            media_type="application/json",
            layer="report",
            produced_by_module="m5",
        ),
        store,
        max_metadata_bytes=65536,
    )

    return project_id, context.id, ctx_art, eval_art


def _dashboard_input_model(
    project_id: str,
    context_snapshot_id: str,
    ctx_art: Artifact,
    eval_art: Artifact,
    *,
    execution_id: str | None = None,
    idempotency_key: str | None = None,
    allow_hypotheses: bool = False,
) -> M8DashboardInput:
    return M8DashboardInput(
        project_id=project_id,
        execution_id=execution_id or f"exec-m8-pg-{uuid4().hex[:8]}",
        module_id="m8",
        contract_version="v1.0",
        context_snapshot_id=context_snapshot_id,
        correlation_id=f"corr-{uuid4().hex[:8]}",
        idempotency_key=idempotency_key or f"idem-{uuid4().hex[:8]}",
        status="requested",
        requested_by="m8-pg-test",
        module_input=M8ModuleInput(
            context_artifacts=[_reference(ctx_art)],
            result_artifacts=[_reference(eval_art)],
            claim_policy=ClaimPolicy(
                required_classification=True,
                require_source_reference=True,
                allow_hypotheses=allow_hypotheses,
            ),
        ),
    )


def test_m8_persists_dashboard_and_lineage_in_postgresql():
    engine = require_migrated_postgres()
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    store = LocalArtifactStore(
        Path(gettempdir()) / f"analytixflow-m8-pg-{uuid4().hex}",
        max_bytes=1024 * 1024,
    )
    orchestrator = ProjectOrchestrator()

    with factory() as db:
        project_id, context_id, ctx_art, eval_art = _setup_pg_project(db, store)
        input_payload = _dashboard_input_model(project_id, context_id, ctx_art, eval_art)

        result = orchestrator.generate_dashboard(
            db,
            project_id,
            input_payload,
            store,
            max_metadata_bytes=65536,
        )

        assert result["status"] == "succeeded"
        assert result["project_id"] == project_id
        assert len(result["artifacts"]) == 1
        dashboard_ref = result["artifacts"][0]
        assert dashboard_ref["artifact_type"] == "dashboard.report"
        assert dashboard_ref["layer"] == "report"

        # Verify Execution in DB
        execution = db.get(Execution, input_payload.execution_id)
        assert execution is not None
        assert execution.status == "succeeded"
        assert execution.output_hash == result["output_hash"]

        # Verify Artifact in DB
        dashboard_db_art = db.scalars(
            select(Artifact).where(
                Artifact.project_id == project_id,
                Artifact.artifact_type == "dashboard.report",
            )
        ).first()
        assert dashboard_db_art is not None
        assert dashboard_db_art.layer == "report"
        assert dashboard_db_art.produced_by_module == "m8"

        # Verify Lineage in DB
        lineage_entries = list(
            db.scalars(
                select(ArtifactLineage).where(
                    ArtifactLineage.project_id == project_id,
                    ArtifactLineage.child_artifact_id == dashboard_db_art.id,
                )
            )
        )
        assert len(lineage_entries) == 2
        parent_ids = {entry.parent_artifact_id for entry in lineage_entries}
        assert ctx_art.id in parent_ids
        assert eval_art.id in parent_ids

        # Verify Audit Event in DB
        audit_events = list(
            db.scalars(
                select(AuditEvent).where(
                    AuditEvent.project_id == project_id,
                    AuditEvent.entity_id == execution.id,
                )
            )
        )
        actions = [e.action for e in audit_events]
        assert "execution.started" in actions
        assert "execution.succeeded" in actions


def test_m8_idempotent_replay_and_conflict_in_postgresql():
    engine = require_migrated_postgres()
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    store = LocalArtifactStore(
        Path(gettempdir()) / f"analytixflow-m8-pg-idem-{uuid4().hex}",
        max_bytes=1024 * 1024,
    )
    orchestrator = ProjectOrchestrator()

    with factory() as db:
        project_id, context_id, ctx_art, eval_art = _setup_pg_project(db, store)
        exec_id = f"exec-m8-idem-{uuid4().hex[:8]}"
        idem_key = f"idem-key-{uuid4().hex[:8]}"

        payload1 = _dashboard_input_model(
            project_id, context_id, ctx_art, eval_art, execution_id=exec_id, idempotency_key=idem_key
        )

        # 1. First execution
        res1 = orchestrator.generate_dashboard(
            db, project_id, payload1, store, max_metadata_bytes=65536
        )

        # 2. Replay same request -> exact same result returned without duplicate execution
        res2 = orchestrator.generate_dashboard(
            db, project_id, payload1, store, max_metadata_bytes=65536
        )
        assert res1["output_hash"] == res2["output_hash"]

        exec_count = len(
            list(
                db.scalars(
                    select(Execution).where(
                        Execution.project_id == project_id,
                        Execution.idempotency_key == idem_key,
                    )
                )
            )
        )
        assert exec_count == 1

        # 3. Conflict: same idempotency key with different payload
        payload_conflict = _dashboard_input_model(
            project_id,
            context_id,
            ctx_art,
            eval_art,
            execution_id=exec_id,
            idempotency_key=idem_key,
            allow_hypotheses=True,
        )
        with pytest.raises(ConflictError):
            orchestrator.generate_dashboard(
                db, project_id, payload_conflict, store, max_metadata_bytes=65536
            )


def test_m8_project_isolation_in_postgresql():
    engine = require_migrated_postgres()
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    store = LocalArtifactStore(
        Path(gettempdir()) / f"analytixflow-m8-pg-iso-{uuid4().hex}",
        max_bytes=1024 * 1024,
    )
    orchestrator = ProjectOrchestrator()

    with factory() as db:
        proj_a, ctx_a, ctx_art_a, eval_art_a = _setup_pg_project(db, store, "Project A")
        proj_b, ctx_b, ctx_art_b, eval_art_b = _setup_pg_project(db, store, "Project B")

        # Project A tries to reference Project B's artifact -> must be rejected
        alien_payload = _dashboard_input_model(
            proj_a, ctx_a, ctx_art_a, eval_art_b
        )
        with pytest.raises((NotFoundError, ValidationError)):
            orchestrator.generate_dashboard(
                db, proj_a, alien_payload, store, max_metadata_bytes=65536
            )

        # Generate dashboard for Project A
        valid_payload_a = _dashboard_input_model(proj_a, ctx_a, ctx_art_a, eval_art_a)
        orchestrator.generate_dashboard(
            db, proj_a, valid_payload_a, store, max_metadata_bytes=65536
        )

        # Project B has no dashboard -> get_latest_dashboard must raise NotFoundError
        with pytest.raises(NotFoundError):
            orchestrator.get_latest_dashboard(db, proj_b, store)


def test_m8_atomic_rollback_on_failure_in_postgresql():
    engine = require_migrated_postgres()
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    store = LocalArtifactStore(
        Path(gettempdir()) / f"analytixflow-m8-pg-atomic-{uuid4().hex}",
        max_bytes=1024 * 1024,
    )
    orchestrator = ProjectOrchestrator()

    with factory() as db:
        project_id, context_id, ctx_art, eval_art = _setup_pg_project(db, store)
        exec_id = f"exec-m8-fail-{uuid4().hex[:8]}"

        # Corrupt the content_hash
        corrupted_eval = _reference(eval_art)
        corrupted_eval["content_hash"] = "sha256:" + "0" * 64

        bad_payload = M8DashboardInput(
            project_id=project_id,
            execution_id=exec_id,
            module_id="m8",
            contract_version="v1.0",
            context_snapshot_id=context_id,
            correlation_id="corr-fail",
            idempotency_key="idem-fail",
            status="requested",
            requested_by="fail-tester",
            module_input=M8ModuleInput(
                context_artifacts=[_reference(ctx_art)],
                result_artifacts=[corrupted_eval],
                claim_policy=ClaimPolicy(
                    required_classification=True,
                    require_source_reference=True,
                    allow_hypotheses=False,
                ),
            ),
        )

        with pytest.raises(ValidationError):
            orchestrator.generate_dashboard(
                db, project_id, bad_payload, store, max_metadata_bytes=65536
            )

        # Verify that no dashboard artifact was persisted
        db_arts = list(
            db.scalars(
                select(Artifact).where(
                    Artifact.project_id == project_id,
                    Artifact.artifact_type == "dashboard.report",
                )
            )
        )
        assert len(db_arts) == 0

        # Verify execution record is marked failed_terminal
        failed_exec = db.get(Execution, exec_id)
        assert failed_exec is not None
        assert failed_exec.status == "failed_terminal"
