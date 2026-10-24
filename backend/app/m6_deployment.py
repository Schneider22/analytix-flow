from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from .db.models import Approval, Artifact, Execution, Project, ProjectContextSnapshot
from .domain.hashing import canonical_json, sha256_canonical
from .domain.sanitization import redact_sensitive
from .repositories import ExecutionRepository
from .schemas import (
    ApprovalCreate,
    ArtifactCreate,
    ArtifactReferenceInput,
    M6DeploymentRequest,
)
from .services import (
    ConflictError,
    NotFoundError,
    ValidationError,
    _verified_storage,
    artifacts,
    commit,
    create_approval,
    create_artifact,
    record_audit,
    require_project,
)
from .storage import ArtifactStore, ArtifactStoreError


class M6DeploymentModule:
    """Prepare a locally consumable deployment package without executing it.

    M6 deliberately stops at a human-gated, immutable package and deployment
    plan. It never deserializes or executes a model binary, starts a process,
    builds a container, creates cloud resources or calls an external provider.
    """

    module_id = "m6"
    contract_version = "v1.0"

    def __init__(self) -> None:
        self.executions = ExecutionRepository()

    def execute(
        self,
        db: Session,
        project_id: str,
        payload: M6DeploymentRequest,
        artifact_store: ArtifactStore,
        *,
        max_metadata_bytes: int,
    ) -> dict[str, Any]:
        self._validate_request(project_id, payload)
        project = require_project(db, project_id)
        context = db.get(ProjectContextSnapshot, payload.context_snapshot_id)
        if context is None or context.project_id != project_id:
            raise NotFoundError("Context snapshot not found for project")

        input_hash = sha256_canonical(payload.model_dump(mode="json"))
        locked_project = db.get(Project, project_id, with_for_update=True)
        if locked_project is None:
            raise NotFoundError("Project not found")

        existing = self.executions.get_by_idempotency(
            db, project_id, self.module_id, payload.idempotency_key
        )
        if existing is not None:
            if existing.input_hash != input_hash or existing.id != payload.execution_id:
                raise ConflictError("The idempotency key is already bound to another M6 execution")
            if existing.result_json is not None:
                return existing.result_json
            raise ConflictError("The idempotent M6 execution is already running")

        existing_by_id = self.executions.get(db, payload.execution_id)
        if existing_by_id is not None:
            raise ConflictError("execution_id is already in use")

        now = datetime.now(timezone.utc)
        execution = Execution(
            id=payload.execution_id,
            project_id=project_id,
            module_id=self.module_id,
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
            module_id=self.module_id,
            correlation_id=payload.correlation_id,
            input_hash=input_hash,
            metadata={"contract_version": payload.contract_version},
        )
        commit(db)

        staged_storage_ids: list[str] = []
        try:
            selected_model, model_approval = self._load_selected_model(
                db, project_id, payload, artifact_store
            )
            package_ref, config_ref = self._persist_package(
                db,
                project_id,
                execution,
                payload,
                selected_model,
                model_approval,
                artifact_store,
                max_metadata_bytes=max_metadata_bytes,
                staged_storage_ids=staged_storage_ids,
            )
            deployment_approval = create_approval(
                db,
                project_id,
                ApprovalCreate(
                    action="approve_deployment_action",
                    scope_type="artifact",
                    artifact_id=package_ref["artifact_id"],
                    artifact_version=package_ref["artifact_version"],
                    requested_by=payload.requested_by or "m6-system",
                    reason=(
                        "Approve the exact immutable M6 package and its local-only "
                        "deployment plan. No process, image or cloud action is executed by M6."
                    ),
                ),
                correlation_id=payload.correlation_id,
                commit_transaction=False,
            )
            deployment_approval_ref = self._approval_reference(deployment_approval, package_ref)
            output = self._result_envelope(
                payload,
                status="awaiting_approval",
                artifacts=[package_ref, config_ref],
                approval_refs=[model_approval, deployment_approval_ref],
                warnings=list(payload.warnings),
                next_actions=[
                    {
                        "action": "approve_deployment_action",
                        "requires_approval": True,
                        "target_module": "m6",
                    }
                ],
                package_artifacts=[package_ref],
                config_ref=config_ref,
            )
            return self._persist_output(
                db,
                execution,
                output,
                input_hash=input_hash,
                correlation_id=payload.correlation_id,
            )
        except (ValidationError, NotFoundError, ConflictError) as exc:
            self._cleanup_staged_artifacts(artifact_store, staged_storage_ids)
            self._fail_execution(db, execution.id, payload, input_hash, str(exc))
            raise
        except ArtifactStoreError as exc:
            self._cleanup_staged_artifacts(artifact_store, staged_storage_ids)
            self._fail_execution(
                db,
                execution.id,
                payload,
                input_hash,
                "Artifact storage failed during M6 package preparation",
            )
            raise ValidationError("Artifact storage failed during deployment preparation") from exc
        except Exception as exc:
            self._cleanup_staged_artifacts(artifact_store, staged_storage_ids)
            self._fail_execution(
                db,
                execution.id,
                payload,
                input_hash,
                "Unexpected M6 deployment preparation failure",
            )
            raise RuntimeError("M6 deployment preparation failed") from exc

    def _validate_request(self, project_id: str, payload: M6DeploymentRequest) -> None:
        if payload.project_id != project_id:
            raise ValidationError("project_id in the contract does not match the URL scope")
        if payload.module_id != self.module_id:
            raise ValidationError("M6 execution requires module_id='m6'")
        if payload.contract_version != self.contract_version:
            raise ValidationError("M6 requires contract_version='v1.0'")
        if payload.status not in {"requested", "ready"}:
            raise ValidationError("M6 executions must start in requested or ready status")
        if payload.module_input.deployment_target.cloud_execution_allowed is not False:
            raise ValidationError("M6 cannot execute cloud actions")
        if payload.module_input.runtime_policy.secret_access == "declared_runtime_secrets":
            raise ValidationError(
                "M6 accepts only secret-free local package preparation in the MVP"
            )
        if not payload.module_input.selected_model.version_id:
            raise ValidationError("selected_model requires the exact physical version_id")
        if len(
            {
                (reference.approval_id, reference.action)
                for reference in payload.approval_refs
            }
        ) != len(payload.approval_refs):
            raise ValidationError("approval_refs must not contain duplicate approval identities")

    def _load_selected_model(
        self,
        db: Session,
        project_id: str,
        payload: M6DeploymentRequest,
        artifact_store: ArtifactStore,
    ) -> tuple[Artifact, dict[str, Any]]:
        reference = payload.module_input.selected_model
        model = artifacts.get_by_logical_version(
            db, project_id, reference.artifact_id, reference.artifact_version
        )
        if model is None:
            raise NotFoundError("Selected model artifact not found for project")
        self._validate_artifact_reference(model, reference)
        if model.artifact_type != "model.pipeline" or model.layer != "model":
            raise ValidationError("M6 selected_model must be a model.pipeline artifact in the model layer")
        if model.produced_by_module != "m4" or not model.source_execution_id:
            raise ValidationError("M6 selected_model must be produced by a successful M4 execution")
        _verified_storage(artifact_store, model.storage_id, model.content_hash)

        source_execution = db.get(Execution, model.source_execution_id)
        if (
            source_execution is None
            or source_execution.project_id != project_id
            or source_execution.module_id != "m4"
            or source_execution.status != "succeeded"
            or not isinstance(source_execution.result_json, dict)
        ):
            raise ValidationError("M6 selected_model does not reference a successful M4 execution")
        module_output = source_execution.result_json.get("module_output")
        if not isinstance(module_output, dict):
            raise ValidationError("M6 selected_model references a malformed M4 result")
        candidates = module_output.get("candidates")
        if not isinstance(candidates, list):
            raise ValidationError("M6 selected_model references a malformed M4 candidate list")
        if not any(
            isinstance(candidate, dict)
            and self._same_reference(candidate.get("pipeline_artifact"), model)
            for candidate in candidates
        ):
            raise ValidationError("M6 selected_model is not present in its M4 execution result")

        matches = [
            item
            for item in payload.approval_refs
            if item.action == "accept_model"
            and item.scope_type == "artifact"
            and item.status == "approved"
            and item.artifact_id == model.logical_id
            and item.artifact_version == model.artifact_version
        ]
        if len(matches) != 1:
            raise ValidationError(
                "M6 requires one approved accept_model approval for the exact selected model version"
            )
        reference_approval = matches[0]
        approval = db.get(Approval, reference_approval.approval_id)
        if (
            approval is None
            or approval.project_id != project_id
            or approval.action != "accept_model"
            or approval.scope_type != "artifact"
            or approval.status != "approved"
            or approval.artifact_id != model.id
            or approval.artifact_version != model.artifact_version
            or approval.scope_hash != reference_approval.scope_hash
        ):
            raise ValidationError("The model approval does not match the exact project-scoped artifact version")
        return model, self._approval_reference(approval, self._artifact_reference(model))

    def _persist_package(
        self,
        db: Session,
        project_id: str,
        execution: Execution,
        payload: M6DeploymentRequest,
        model: Artifact,
        model_approval: dict[str, Any],
        artifact_store: ArtifactStore,
        *,
        max_metadata_bytes: int,
        staged_storage_ids: list[str],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        digest = sha256_canonical(execution.id)[7:23]
        package_id = f"m6-deployment-{digest}-package"
        config_id = f"m6-deployment-{digest}-config"
        model_ref = self._artifact_reference(model)
        safe_target = redact_sensitive(payload.module_input.deployment_target.model_dump(mode="json"))
        safe_api_contract = redact_sensitive(payload.module_input.api_contract.model_dump(mode="json"))
        runtime_policy = payload.module_input.runtime_policy.model_dump(mode="json")
        config_payload = {
            "format": "analytixflow.m6.configuration.v1",
            "execution_id": execution.id,
            "selected_model": model_ref,
            "api_contract": safe_api_contract,
            "deployment_target": safe_target,
            "runtime_policy": runtime_policy,
            "execution_mode": "plan_only",
            "cloud_execution_allowed": False,
        }
        config_stored = artifact_store.put(canonical_json(config_payload).encode("utf-8"))
        staged_storage_ids.append(config_stored.storage_id)
        config = create_artifact(
            db,
            project_id,
            ArtifactCreate(
                artifact_id=config_id,
                artifact_type="deployment.config",
                artifact_version="v1",
                content_hash=config_stored.content_hash,
                storage_id=config_stored.storage_id,
                uri=config_stored.uri,
                media_type="application/json",
                layer="deployment",
                produced_by_module=self.module_id,
                source_execution_id=execution.id,
                parent_artifact_refs=[
                    ArtifactReferenceInput(
                        artifact_id=model.logical_id,
                        artifact_version=model.artifact_version,
                    )
                ],
                metadata={
                    "target_type": payload.module_input.deployment_target.target_type,
                    "plan_only": True,
                    "secret_access": runtime_policy["secret_access"],
                },
            ),
            artifact_store,
            max_metadata_bytes=max_metadata_bytes,
            correlation_id=payload.correlation_id,
            commit_transaction=False,
        )
        config_ref = self._artifact_reference(config)

        package_payload = {
            "format": "analytixflow.m6.deployment-package.v1",
            "execution_id": execution.id,
            "selected_model": model_ref,
            "configuration_artifact": config_ref,
            "accepted_model_approval": model_approval,
            "target_type": payload.module_input.deployment_target.target_type,
            "model_content_hash": model.content_hash,
            "package_mode": {
                "local_process": "local_process_descriptor",
                "docker_artifact": "docker_build_context_descriptor",
                "cloud_plan_only": "cloud_plan_descriptor",
            }[payload.module_input.deployment_target.target_type],
            "execution_mode": "plan_only",
            "cloud_execution_allowed": False,
            "model_binary_deserialized": False,
            "cloud_resources_created": False,
        }
        package_stored = artifact_store.put(canonical_json(package_payload).encode("utf-8"))
        staged_storage_ids.append(package_stored.storage_id)
        package = create_artifact(
            db,
            project_id,
            ArtifactCreate(
                artifact_id=package_id,
                artifact_type="deployment.package",
                artifact_version="v1",
                content_hash=package_stored.content_hash,
                storage_id=package_stored.storage_id,
                uri=package_stored.uri,
                media_type="application/json",
                layer="deployment",
                produced_by_module=self.module_id,
                source_execution_id=execution.id,
                parent_artifact_refs=[
                    ArtifactReferenceInput(
                        artifact_id=model.logical_id,
                        artifact_version=model.artifact_version,
                    ),
                    ArtifactReferenceInput(
                        artifact_id=config.logical_id,
                        artifact_version=config.artifact_version,
                    ),
                ],
                metadata={
                    "target_type": payload.module_input.deployment_target.target_type,
                    "plan_only": True,
                    "model_content_hash": model.content_hash,
                },
            ),
            artifact_store,
            max_metadata_bytes=max_metadata_bytes,
            correlation_id=payload.correlation_id,
            commit_transaction=False,
        )
        return self._artifact_reference(package), config_ref

    def _result_envelope(
        self,
        payload: M6DeploymentRequest,
        *,
        status: str,
        artifacts: list[dict[str, Any]],
        approval_refs: list[dict[str, Any]],
        warnings: list[str],
        next_actions: list[dict[str, Any]],
        package_artifacts: list[dict[str, Any]],
        config_ref: dict[str, Any],
    ) -> dict[str, Any]:
        target = payload.module_input.deployment_target.target_type
        limitations = [
            "M6 may read model bytes only to verify SHA-256; it does not deserialize or execute them.",
            "M6 does not start a local process or build a Docker image.",
            "M6 does not create cloud resources or invoke paid services.",
            "Deployment remains blocked until the exact package approval is resolved by a human.",
        ]
        if target == "cloud_plan_only":
            limitations.append("The cloud target is informational only and has no cloud side effect in the MVP.")
        output = {
            "project_id": payload.project_id,
            "execution_id": payload.execution_id,
            "module_id": self.module_id,
            "contract_version": payload.contract_version,
            "context_snapshot_id": payload.context_snapshot_id,
            "correlation_id": payload.correlation_id,
            "status": status,
            "artifacts": artifacts,
            "approval_refs": approval_refs,
            "warnings": warnings,
            "errors": [],
            "next_actions": next_actions,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "module_output": {
                "package_artifacts": package_artifacts,
                "validation_report": {
                    "status": "passed_with_warnings",
                    "tests": [
                        {"name": "project_scope", "status": "passed", "classification": "security"},
                        {"name": "selected_model_reference", "status": "passed", "classification": "traceability"},
                        {"name": "artifact_store_integrity", "status": "passed", "classification": "integrity"},
                        {"name": "human_approval_gate", "status": "passed", "classification": "control"},
                    ],
                    "limitations": limitations,
                },
                "deployment_plan": {
                    "target_type": target,
                    "configuration_artifact": config_ref,
                    "permissions": [
                        "read_project_scoped_model_artifact",
                        "read_project_scoped_deployment_artifact",
                        "network_access_denied_by_default",
                        "no_secret_values_persisted",
                    ],
                    "rollback_plan": (
                        "Do not activate the package; retain immutable artifacts and resolve a new "
                        "approval for any subsequent package version."
                    ),
                    "cost_status": "not_applicable" if target != "cloud_plan_only" else "not_available",
                    "cloud_execution_allowed": False,
                    "approval_request": {
                        "action": "approve_deployment_action",
                        "reason": (
                            "Human approval is required for the exact immutable package before any "
                            "future deployment action."
                        ),
                    },
                },
            },
        }
        return output

    def _persist_output(
        self,
        db: Session,
        execution: Execution,
        output: dict[str, Any],
        *,
        input_hash: str,
        correlation_id: str,
    ) -> dict[str, Any]:
        execution.status = output["status"]
        execution.output_hash = sha256_canonical(output)
        execution.result_json = output
        execution.completed_at = datetime.now(timezone.utc)
        record_audit(
            db,
            project_id=execution.project_id,
            action="execution.awaiting_approval",
            entity_type="execution",
            entity_id=execution.id,
            module_id=self.module_id,
            correlation_id=correlation_id,
            input_hash=input_hash,
            output_hash=execution.output_hash,
            metadata={"status": output["status"]},
        )
        commit(db)
        return output

    def _fail_execution(
        self,
        db: Session,
        execution_id: str,
        payload: M6DeploymentRequest,
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
            module_id=self.module_id,
            correlation_id=payload.correlation_id,
            input_hash=input_hash,
            metadata={"status": "failed_terminal", "error": "M6 deployment preparation failed"},
        )
        commit(db)

    @staticmethod
    def _validate_artifact_reference(artifact: Artifact, reference: Any) -> None:
        if artifact.id != reference.version_id:
            raise ValidationError("selected_model version_id does not match the server artifact")
        if artifact.logical_id != reference.artifact_id:
            raise ValidationError("selected_model artifact_id does not match the server artifact")
        if artifact.artifact_type != reference.artifact_type:
            raise ValidationError("selected_model artifact_type does not match the server artifact")
        if artifact.artifact_version != reference.artifact_version:
            raise ValidationError("selected_model artifact_version does not match the server artifact")
        if artifact.version_number != reference.version_number:
            raise ValidationError("selected_model version_number does not match the server artifact")
        if artifact.content_hash != reference.content_hash:
            raise ValidationError("selected_model content_hash does not match the server artifact")

    @staticmethod
    def _same_reference(reference: Any, artifact: Artifact) -> bool:
        return isinstance(reference, dict) and (
            reference.get("artifact_id") == artifact.logical_id
            and reference.get("artifact_type") == artifact.artifact_type
            and reference.get("artifact_version") == artifact.artifact_version
            and reference.get("version_number") == artifact.version_number
            and reference.get("version_id") == artifact.id
            and reference.get("content_hash") == artifact.content_hash
        )

    @staticmethod
    def _artifact_reference(artifact: Artifact) -> dict[str, Any]:
        reference = {
            "artifact_id": artifact.logical_id,
            "artifact_type": artifact.artifact_type,
            "artifact_version": artifact.artifact_version,
            "version_number": artifact.version_number,
            "version_id": artifact.id,
            "content_hash": artifact.content_hash,
        }
        optional = {
            "predecessor_version_id": artifact.predecessor_artifact_id,
            "uri": artifact.uri,
            "media_type": artifact.media_type,
            "layer": artifact.layer,
            "produced_by_module": artifact.produced_by_module,
            "created_at": artifact.created_at.isoformat() if artifact.created_at else None,
        }
        reference.update({key: value for key, value in optional.items() if value is not None})
        return reference

    @staticmethod
    def _approval_reference(approval: Approval, artifact_ref: dict[str, Any]) -> dict[str, Any]:
        reference = {
            "approval_id": approval.id,
            "action": approval.action,
            "scope_type": approval.scope_type,
            "status": approval.status,
            "scope_hash": approval.scope_hash,
            "artifact_id": artifact_ref["artifact_id"],
            "artifact_version": artifact_ref["artifact_version"],
        }
        if approval.resolved_by:
            reference["approved_by"] = approval.resolved_by
        if approval.resolved_at:
            reference["approved_at"] = approval.resolved_at.isoformat()
        if approval.reason:
            reference["reason"] = approval.reason
        return reference

    @staticmethod
    def _cleanup_staged_artifacts(artifact_store: ArtifactStore, storage_ids: list[str]) -> None:
        for storage_id in storage_ids:
            try:
                artifact_store.delete(storage_id)
            except (ArtifactStoreError, OSError):
                pass
        storage_ids.clear()
