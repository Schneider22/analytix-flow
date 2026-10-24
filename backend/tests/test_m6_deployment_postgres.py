from __future__ import annotations

import shutil
from pathlib import Path
from tempfile import gettempdir
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.db.models import Artifact, ArtifactLineage, Execution, Project
from app.m6_deployment import M6DeploymentModule
from app.schemas import (
    ApprovalCreate,
    ApprovalResolve,
    ArtifactCreate,
    ContextCreate,
    M6DeploymentRequest,
)
from app.services import create_approval, create_artifact, create_context_snapshot, resolve_approval
from app.storage import LocalArtifactStore
from tests.postgres_support import require_migrated_postgres
from tests.test_m6_deployment import _assert_m6_output_contract


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


def test_m6_persists_project_scoped_package_and_lineage_in_postgresql():
    engine = require_migrated_postgres()
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    project_id = str(uuid4())
    execution_id = f"m4-pg-m6-{uuid4().hex}"
    m6_execution_id = f"m6-pg-{uuid4().hex}"
    store = LocalArtifactStore(
        Path(gettempdir()) / f"analytixflow-m6-pg-{uuid4().hex}",
        max_bytes=1024 * 1024,
    )
    try:
        with factory() as db:
            db.add(
                Project(
                    id=project_id,
                    company_name="M6 PostgreSQL Test",
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
                        "company_name": "M6 PostgreSQL Test",
                        "company_description": "Synthetic",
                        "business_need": "Synthetic",
                        "expected_objective": "Synthetic",
                        "business_rules": [],
                        "constraints": [],
                        "assumptions": [],
                        "success_criteria": ["Synthetic"],
                    },
                    created_by="m6-test",
                ),
            )
            m4 = Execution(
                id=execution_id,
                project_id=project_id,
                module_id="m4",
                contract_version="v1.0",
                context_snapshot_id=context.id,
                status="succeeded",
                idempotency_key=f"key-{execution_id}",
                correlation_id=f"corr-{execution_id}",
                input_hash="sha256:" + "1" * 64,
                result_json={"module_output": {"candidates": []}},
            )
            db.add(m4)
            db.flush()
            stored = store.put(b"synthetic-model-payload")
            model = create_artifact(
                db,
                project_id,
                ArtifactCreate(
                    artifact_id=f"model-{uuid4().hex}",
                    artifact_type="model.pipeline",
                    artifact_version="v1",
                    content_hash=stored.content_hash,
                    storage_id=stored.storage_id,
                    media_type="application/octet-stream",
                    layer="model",
                    produced_by_module="m4",
                    source_execution_id=execution_id,
                ),
                store,
                max_metadata_bytes=262144,
            )
            model_ref = _reference(model)
            m4.result_json = {"module_output": {"candidates": [{"pipeline_artifact": model_ref}]}}
            db.commit()
            approval = create_approval(
                db,
                project_id,
                ApprovalCreate(
                    action="accept_model",
                    scope_type="artifact",
                    artifact_id=model.logical_id,
                    artifact_version=model.artifact_version,
                    requested_by="m6-reviewer",
                ),
            )
            resolved = resolve_approval(
                db,
                project_id,
                approval.id,
                ApprovalResolve(status="approved", resolved_by="m6-approver"),
            )
            payload = M6DeploymentRequest.model_validate(
                {
                    "project_id": project_id,
                    "execution_id": m6_execution_id,
                    "module_id": "m6",
                    "contract_version": "v1.0",
                    "context_snapshot_id": context.id,
                    "status": "requested",
                    "correlation_id": f"corr-{m6_execution_id}",
                    "idempotency_key": f"key-{m6_execution_id}",
                    "requested_by": "m6-requester",
                    "module_input": {
                        "selected_model": model_ref,
                        "deployment_target": {
                            "target_type": "local_process",
                            "cloud_execution_allowed": False,
                            "configuration": {"port": 8000},
                        },
                        "api_contract": {
                            "operation": "predict",
                            "request_schema": {"type": "object"},
                            "response_schema": {"type": "object"},
                        },
                        "runtime_policy": {
                            "network_access": "denied",
                            "secret_access": "none",
                        },
                    },
                    "approval_refs": [
                        {
                            "approval_id": resolved.id,
                            "action": resolved.action,
                            "scope_type": resolved.scope_type,
                            "status": resolved.status,
                            "scope_hash": resolved.scope_hash,
                            "artifact_id": model.logical_id,
                            "artifact_version": model.artifact_version,
                            "approved_by": resolved.resolved_by,
                            "approved_at": resolved.resolved_at,
                        }
                    ],
                }
            )
            result = M6DeploymentModule().execute(
                db, project_id, payload, store, max_metadata_bytes=262144
            )
            assert result["status"] == "awaiting_approval"
            _assert_m6_output_contract(result)
            package_id = result["module_output"]["package_artifacts"][0]["version_id"]
            package = db.get(Artifact, package_id)
            assert package is not None
            assert package.project_id == project_id
            assert package.artifact_type == "deployment.package"
            links = list(
                db.scalars(
                    select(ArtifactLineage).where(
                        ArtifactLineage.project_id == project_id,
                        ArtifactLineage.child_artifact_id == package.id,
                    )
                )
            )
            assert {link.parent_artifact_id for link in links} == {
                model.id,
                result["module_output"]["deployment_plan"]["configuration_artifact"]["version_id"],
            }
    finally:
        shutil.rmtree(store.root, ignore_errors=True)
        engine.dispose()
