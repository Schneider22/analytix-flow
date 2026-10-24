from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.db.models import Artifact, ArtifactLineage, Execution, Project
from app.m4_modeling import M4ModelingModule
from app.m5_evaluation import M5EvaluationModule
from app.schemas import (
    ApprovalCreate,
    ApprovalResolve,
    ArtifactCreate,
    ContextCreate,
    M4ModelingRequest,
    M5EvaluationRequest,
)
from app.services import (
    ConflictError,
    create_artifact,
    create_context_snapshot,
    create_approval,
    resolve_approval,
)
from app.storage import LocalArtifactStore
from tests.postgres_support import require_migrated_postgres
from tests.test_m4_modeling_postgres import _contract_ref


def test_m5_persists_project_scoped_evaluation_report_in_postgresql():
    engine = require_migrated_postgres()
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    project_id = str(uuid4())
    m4_execution_id = f"m4-pg-m5-{uuid4().hex}"
    m5_execution_id = f"m5-pg-{uuid4().hex}"
    store = LocalArtifactStore(
        Path("/tmp") / f"analytixflow-m5-pg-{uuid4().hex}",
        max_bytes=1024 * 1024,
    )
    try:
        with factory() as db:
            db.add(
                Project(
                    id=project_id,
                    company_name="M5 PostgreSQL Test",
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
                        "company_name": "M5 PostgreSQL Test",
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
            m4_payload = M4ModelingRequest.model_validate(
                {
                    "project_id": project_id,
                    "execution_id": m4_execution_id,
                    "module_id": "m4",
                    "contract_version": "v1.0",
                    "context_snapshot_id": context.id,
                    "status": "requested",
                    "correlation_id": f"corr-{m4_execution_id}",
                    "idempotency_key": f"key-{m4_execution_id}",
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
            m4_result = M4ModelingModule().execute(
                db, project_id, m4_payload, store, max_metadata_bytes=262144
            )
            pipeline = next(
                item["pipeline_artifact"]
                for item in m4_result["module_output"]["candidates"]
                if item["technique"] == "logistic_regression"
            )
            approval = create_approval(
                db,
                project_id,
                ApprovalCreate(
                    action="select_model_candidate",
                    scope_type="artifact",
                    artifact_id=pipeline["artifact_id"],
                    artifact_version=pipeline["artifact_version"],
                    requested_by="m5-reviewer",
                ),
            )
            resolved = resolve_approval(
                db,
                project_id,
                approval.id,
                ApprovalResolve(status="approved", resolved_by="m5-approver"),
            )
            m5_payload = M5EvaluationRequest.model_validate(
                {
                    "project_id": project_id,
                    "execution_id": m5_execution_id,
                    "module_id": "m5",
                    "contract_version": "v1.0",
                    "context_snapshot_id": context.id,
                    "status": "requested",
                    "correlation_id": f"corr-{m5_execution_id}",
                    "idempotency_key": f"key-{m5_execution_id}",
                    "module_input": {
                        "candidate_models": [pipeline],
                        "gold_dataset": _contract_ref(gold),
                        "baseline": {
                            "description": "Synthetic majority-class baseline",
                            "artifact_or_method": "majority_class_baseline",
                        },
                        "evaluation_policy": {
                            "primary_metrics": ["f1_macro"],
                            "secondary_metrics": ["accuracy"],
                            "validation_strategy": "holdout",
                        },
                        "success_criteria": ["Synthetic criteria require review"],
                    },
                    "approval_refs": [
                        {
                            "approval_id": resolved.id,
                            "action": resolved.action,
                            "scope_type": resolved.scope_type,
                            "status": resolved.status,
                            "scope_hash": resolved.scope_hash,
                            "artifact_id": pipeline["artifact_id"],
                            "artifact_version": pipeline["artifact_version"],
                            "approved_by": resolved.resolved_by,
                            "approved_at": resolved.resolved_at,
                        }
                    ],
                }
            )
            result = M5EvaluationModule().execute(
                db, project_id, m5_payload, store, max_metadata_bytes=262144
            )
            assert result["status"] == "awaiting_approval"
            assert result["module_output"]["recommendation"]["status"] == "insufficient_evidence"
            report_id = result["module_output"]["evaluation_report"]["version_id"]
            report = db.get(Artifact, report_id)
            assert report is not None
            assert report.project_id == project_id
            assert report.artifact_type == "evaluation.m5"
            report_lineage = list(
                db.scalars(
                    select(ArtifactLineage).where(
                        ArtifactLineage.project_id == project_id,
                        ArtifactLineage.child_artifact_id == report.id,
                    )
                )
            )
            assert len(report_lineage) == 3
            assert all(link.project_id == project_id for link in report_lineage)
            concurrent_payload = M5EvaluationRequest.model_validate(
                {
                    **m5_payload.model_dump(mode="json"),
                    "execution_id": f"{m5_execution_id}-concurrent",
                    "idempotency_key": f"key-{m5_execution_id}-concurrent",
                }
            )

            def run_concurrent():
                with factory() as concurrent_db:
                    try:
                        return ("succeeded", M5EvaluationModule().execute(
                            concurrent_db,
                            project_id,
                            concurrent_payload,
                            store,
                            max_metadata_bytes=262144,
                        ))
                    except ConflictError:
                        return ("conflict", None)

            with ThreadPoolExecutor(max_workers=2) as executor:
                concurrent_results = list(executor.map(lambda _: run_concurrent(), range(2)))
            assert all(status in {"succeeded", "conflict"} for status, _ in concurrent_results)
            successful_results = [result for status, result in concurrent_results if status == "succeeded"]
            assert successful_results
            if len(successful_results) == 2:
                assert successful_results[0] == successful_results[1]
            with factory() as verification_db:
                assert verification_db.get(Execution, concurrent_payload.execution_id) is not None
                report_ids = verification_db.scalars(
                    select(Artifact.id).where(
                        Artifact.project_id == project_id,
                        Artifact.source_execution_id == concurrent_payload.execution_id,
                        Artifact.artifact_type == "evaluation.m5",
                    )
                ).all()
                assert len(report_ids) == 1
            assert M5EvaluationModule().execute(
                db, project_id, m5_payload, store, max_metadata_bytes=262144
            ) == result
    finally:
        engine.dispose()
