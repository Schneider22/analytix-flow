from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .db.models import Artifact, Execution, Project, ProjectContextSnapshot
from .domain.hashing import canonical_json, sha256_canonical
from .m2_ingestion import M2IngestionModule
from .m3_preparation import M3PreparationModule
from .m4_modeling import M4ModelingModule
from .m5_evaluation import M5EvaluationModule
from .m6_deployment import M6DeploymentModule
from .m7_governance import M7GovernanceModule
from .m8_dashboard import M8DashboardModule
from .repositories import ExecutionRepository
from .schemas import (
    ArtifactCreate,
    ArtifactReferenceInput,
    M2IngestionRequest,
    M3PreparationRequest,
    M4ModelingRequest,
    M5EvaluationRequest,
    M6DeploymentRequest,
    M7GovernanceRequest,
    M8DashboardInput,
)
from .services import (
    ConflictError,
    NotFoundError,
    ValidationError,
    _verified_storage,
    artifacts,
    commit,
    create_artifact,
    record_audit,
    require_editable_project,
    require_project,
)
from .storage import ArtifactStore, ArtifactStoreError


class ProjectOrchestrator:
    """Central entry point for module execution.

    Modules remain isolated behind this boundary so no module can invoke
    another module directly.
    """

    def __init__(self) -> None:
        self._m2 = M2IngestionModule()
        self._m3 = M3PreparationModule()
        self._m4 = M4ModelingModule()
        self._m5 = M5EvaluationModule()
        self._m6 = M6DeploymentModule()
        self._m7 = M7GovernanceModule()
        self._m8 = M8DashboardModule()
        self.executions = ExecutionRepository()

    def run_m2(
        self,
        db: Session,
        project_id: str,
        payload: M2IngestionRequest,
        artifact_store: ArtifactStore,
        *,
        max_metadata_bytes: int,
    ) -> dict:
        return self._m2.execute(
            db,
            project_id,
            payload,
            artifact_store,
            max_metadata_bytes=max_metadata_bytes,
        )

    def run_m3(
        self,
        db: Session,
        project_id: str,
        payload: M3PreparationRequest,
        artifact_store: ArtifactStore,
        *,
        max_metadata_bytes: int,
    ) -> dict:
        return self._m3.execute(
            db,
            project_id,
            payload,
            artifact_store,
            max_metadata_bytes=max_metadata_bytes,
        )

    def run_m4(
        self,
        db: Session,
        project_id: str,
        payload: M4ModelingRequest,
        artifact_store: ArtifactStore,
        *,
        max_metadata_bytes: int,
    ) -> dict:
        return self._m4.execute(
            db,
            project_id,
            payload,
            artifact_store,
            max_metadata_bytes=max_metadata_bytes,
        )

    def run_m5(
        self,
        db: Session,
        project_id: str,
        payload: M5EvaluationRequest,
        artifact_store: ArtifactStore,
        *,
        max_metadata_bytes: int,
    ) -> dict:
        return self._m5.execute(
            db,
            project_id,
            payload,
            artifact_store,
            max_metadata_bytes=max_metadata_bytes,
        )

    def run_m6(
        self,
        db: Session,
        project_id: str,
        payload: M6DeploymentRequest,
        artifact_store: ArtifactStore,
        *,
        max_metadata_bytes: int,
    ) -> dict:
        return self._m6.execute(
            db,
            project_id,
            payload,
            artifact_store,
            max_metadata_bytes=max_metadata_bytes,
        )

    def run_m7(
        self,
        db: Session,
        project_id: str,
        payload: M7GovernanceRequest,
        artifact_store: ArtifactStore,
        *,
        max_metadata_bytes: int,
    ) -> dict:
        return self._m7.execute(
            db,
            project_id,
            payload,
            artifact_store,
            max_metadata_bytes=max_metadata_bytes,
        )

    def generate_dashboard(
        self,
        db: Session,
        project_id: str,
        payload: M8DashboardInput,
        artifact_store: ArtifactStore,
        *,
        max_metadata_bytes: int,
    ) -> dict[str, Any]:
        self._validate_dashboard_request(project_id, payload)
        project = require_editable_project(db, project_id)
        context = db.get(ProjectContextSnapshot, payload.context_snapshot_id)
        if context is None or context.project_id != project_id:
            raise NotFoundError("Context snapshot not found for project")

        input_hash = sha256_canonical(payload.model_dump(mode="json"))
        locked_project = db.get(Project, project_id, with_for_update=True)
        if locked_project is None:
            raise NotFoundError("Project not found")

        existing = self.executions.get_by_idempotency(
            db, project_id, "m8", payload.idempotency_key
        )
        if existing is not None:
            if existing.input_hash != input_hash or existing.id != payload.execution_id:
                raise ConflictError("The idempotency key is already bound to another M8 execution")
            if existing.result_json is not None:
                return existing.result_json
            raise ConflictError("The idempotent M8 execution is already running")

        existing_by_id = self.executions.get(db, payload.execution_id)
        if existing_by_id is not None:
            raise ConflictError("execution_id is already in use")

        now = datetime.now(timezone.utc)
        execution = Execution(
            id=payload.execution_id,
            project_id=project_id,
            module_id="m8",
            contract_version=payload.contract_version,
            context_snapshot_id=context.id,
            status="running",
            idempotency_key=payload.idempotency_key,
            correlation_id=payload.correlation_id,
            input_hash=input_hash,
            requested_at=payload.requested_at or now,
            started_at=now,
        )
        self.executions.create(db, execution)
        record_audit(
            db,
            project_id=project_id,
            action="execution.started",
            entity_type="execution",
            entity_id=execution.id,
            module_id="m8",
            correlation_id=payload.correlation_id,
            input_hash=input_hash,
            metadata={"contract_version": payload.contract_version},
        )
        commit(db)

        staged_storage_ids: list[str] = []
        try:
            verified_artifacts = self._verify_referenced_dashboard_artifacts(
                db, project_id, payload, artifact_store
            )

            verified_refs_map = {
                (art.logical_id, art.artifact_version): art
                for art in verified_artifacts
            }
            enriched_context = [
                ref.model_copy(update={"uri": verified_refs_map[(ref.artifact_id, ref.artifact_version)].uri})
                if (ref.artifact_id, ref.artifact_version) in verified_refs_map and not ref.uri
                else ref
                for ref in payload.module_input.context_artifacts
            ]
            enriched_results = [
                ref.model_copy(update={"uri": verified_refs_map[(ref.artifact_id, ref.artifact_version)].uri})
                if (ref.artifact_id, ref.artifact_version) in verified_refs_map and not ref.uri
                else ref
                for ref in payload.module_input.result_artifacts
            ]

            # Call domain engine to build sections, roadmap, and canonical payload
            sections = self._m8.synthesize_sections(
                context_artifacts=enriched_context,
                result_artifacts=enriched_results,
                policy=payload.module_input.claim_policy,
                artifact_store=artifact_store,
                project_id=project_id,
            )
            roadmap = self._m8.build_roadmap(enriched_results)

            report_payload = self._m8.build_canonical_report_payload(
                project_id=project_id,
                execution_id=payload.execution_id,
                sections=sections,
                roadmap=roadmap,
                claim_policy=payload.module_input.claim_policy,
            )

            canonical_bytes = canonical_json(report_payload).encode("utf-8")
            stored = artifact_store.put(canonical_bytes)
            staged_storage_ids.append(stored.storage_id)

            digest = stored.content_hash[7:23]
            dashboard_artifact_id = f"m8-dashboard-report-{digest}"

            parent_refs = [
                ArtifactReferenceInput(
                    artifact_id=art.logical_id,
                    artifact_version=art.artifact_version,
                )
                for art in verified_artifacts
            ]

            artifact = create_artifact(
                db,
                project_id,
                ArtifactCreate(
                    artifact_id=dashboard_artifact_id,
                    artifact_type="dashboard.report",
                    artifact_version="v1",
                    content_hash=stored.content_hash,
                    storage_id=stored.storage_id,
                    uri=stored.uri,
                    media_type="application/json",
                    layer="report",
                    produced_by_module="m8",
                    source_execution_id=execution.id,
                    parent_artifact_refs=parent_refs,
                    metadata={
                        "sections_count": len(sections),
                        "roadmap_items_count": len(roadmap),
                        "claim_policy": payload.module_input.claim_policy.model_dump(mode="json"),
                    },
                ),
                artifact_store,
                max_metadata_bytes=max_metadata_bytes,
                correlation_id=payload.correlation_id,
                commit_transaction=False,
            )

            dashboard_ref_dict = {
                "artifact_id": artifact.logical_id,
                "artifact_type": artifact.artifact_type,
                "artifact_version": artifact.artifact_version,
                "version_number": artifact.version_number,
                "version_id": artifact.id,
                "content_hash": artifact.content_hash,
                "uri": artifact.uri,
                "media_type": artifact.media_type,
                "layer": artifact.layer,
                "produced_by_module": artifact.produced_by_module,
            }

            output = {
                "project_id": payload.project_id,
                "execution_id": payload.execution_id,
                "module_id": "m8",
                "contract_version": payload.contract_version,
                "context_snapshot_id": payload.context_snapshot_id,
                "correlation_id": payload.correlation_id,
                "status": "succeeded",
                "artifacts": [dashboard_ref_dict],
                "approval_refs": [],
                "warnings": list(payload.warnings),
                "errors": [],
                "next_actions": [
                    {
                        "action": "executive_stakeholder_review",
                        "requires_approval": True,
                        "target_module": "m8",
                    }
                ],
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "output_hash": stored.content_hash,
                "module_output": {
                    "dashboard_artifact": dashboard_ref_dict,
                    "sections": [s.model_dump(mode="json", exclude_none=True) for s in sections],
                    "roadmap": [r.model_dump(mode="json", exclude_none=True) for r in roadmap],
                },
            }

            execution.status = "succeeded"
            execution.output_hash = sha256_canonical(output)
            execution.result_json = output
            execution.completed_at = datetime.now(timezone.utc)
            record_audit(
                db,
                project_id=execution.project_id,
                action="execution.succeeded",
                entity_type="execution",
                entity_id=execution.id,
                module_id="m8",
                correlation_id=payload.correlation_id,
                input_hash=input_hash,
                output_hash=execution.output_hash,
                metadata={"status": "succeeded"},
            )
            commit(db)
            return output
        except (ValidationError, NotFoundError, ConflictError) as exc:
            self._cleanup_staged_artifacts(artifact_store, staged_storage_ids)
            self._fail_dashboard_execution(db, execution.id, payload, input_hash, str(exc))
            raise
        except ArtifactStoreError as exc:
            self._cleanup_staged_artifacts(artifact_store, staged_storage_ids)
            self._fail_dashboard_execution(
                db,
                execution.id,
                payload,
                input_hash,
                "Artifact storage failed during dashboard preparation",
            )
            raise ValidationError("Artifact storage failed during dashboard preparation") from exc
        except Exception as exc:
            self._cleanup_staged_artifacts(artifact_store, staged_storage_ids)
            self._fail_dashboard_execution(
                db,
                execution.id,
                payload,
                input_hash,
                "Unexpected M8 dashboard preparation failure",
            )
            raise RuntimeError("M8 dashboard preparation failed") from exc

    def run_m8(
        self,
        db: Session,
        project_id: str,
        payload: M8DashboardInput,
        artifact_store: ArtifactStore,
        *,
        max_metadata_bytes: int,
    ) -> dict[str, Any]:
        return self.generate_dashboard(
            db,
            project_id,
            payload,
            artifact_store,
            max_metadata_bytes=max_metadata_bytes,
        )

    def get_latest_dashboard(
        self,
        db: Session,
        project_id: str,
        artifact_store: ArtifactStore,
    ) -> dict[str, Any]:
        require_project(db, project_id)
        latest_execution = (
            db.scalars(
                select(Execution)
                .where(
                    Execution.project_id == project_id,
                    Execution.module_id == "m8",
                    Execution.status == "succeeded",
                )
                .order_by(Execution.completed_at.desc())
            )
            .first()
        )
        if latest_execution is None or latest_execution.result_json is None:
            raise NotFoundError("No dashboard found for project")
        if latest_execution.project_id != project_id:
            raise ValidationError("Project isolation violation")
        return latest_execution.result_json

    def _validate_dashboard_request(self, project_id: str, payload: M8DashboardInput) -> None:
        if payload.project_id != project_id:
            raise ValidationError("project_id in the contract does not match the URL scope")
        if payload.module_id != "m8":
            raise ValidationError("M8 execution requires module_id='m8'")
        if payload.contract_version != "v1.0":
            raise ValidationError("M8 requires contract_version='v1.0'")
        if payload.status not in {"requested", "ready"}:
            raise ValidationError("M8 executions must start in requested or ready status")

    def _verify_referenced_dashboard_artifacts(
        self,
        db: Session,
        project_id: str,
        payload: M8DashboardInput,
        artifact_store: ArtifactStore,
    ) -> list[Artifact]:
        verified: list[Artifact] = []
        all_refs = (
            payload.module_input.context_artifacts + payload.module_input.result_artifacts
        )
        if not all_refs:
            raise ValidationError("M8 requires at least one context or result artifact")

        for ref in all_refs:
            artifact = artifacts.get_by_logical_version(
                db, project_id, ref.artifact_id, ref.artifact_version
            )
            if artifact is None or artifact.project_id != project_id:
                raise NotFoundError(
                    f"Referenced artifact '{ref.artifact_id}' ({ref.artifact_version}) not found for project"
                )
            if ref.version_id and artifact.id != ref.version_id:
                raise ValidationError(
                    f"Artifact '{ref.artifact_id}' physical version_id does not match server"
                )
            if artifact.content_hash != ref.content_hash:
                raise ValidationError(
                    f"Artifact '{ref.artifact_id}' content_hash does not match server record"
                )
            _verified_storage(artifact_store, artifact.storage_id, artifact.content_hash)
            verified.append(artifact)
        return verified

    def _cleanup_staged_artifacts(
        self, artifact_store: ArtifactStore, staged_storage_ids: list[str]
    ) -> None:
        for storage_id in staged_storage_ids:
            try:
                artifact_store.delete(storage_id)
            except Exception:
                pass

    def _fail_dashboard_execution(
        self,
        db: Session,
        execution_id: str,
        payload: M8DashboardInput,
        input_hash: str,
        message: str,
    ) -> None:
        db.rollback()
        execution = self.executions.get(db, execution_id)
        if execution is None:
            return
        execution.status = "failed_terminal"
        execution.error_summary = message[:1000]
        execution.completed_at = datetime.now(timezone.utc)
        record_audit(
            db,
            project_id=execution.project_id,
            action="execution.failed",
            entity_type="execution",
            entity_id=execution.id,
            module_id="m8",
            correlation_id=payload.correlation_id,
            input_hash=input_hash,
            metadata={"status": "failed_terminal", "error": "M8 dashboard preparation failed"},
        )
        commit(db)
