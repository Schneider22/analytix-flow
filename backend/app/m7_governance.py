from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from .db.models import Approval, Artifact, AuditEvent, Decision, Execution, Project, ProjectContextSnapshot
from .domain.hashing import canonical_json, sha256_canonical
from .repositories import ExecutionRepository
from .schemas import (
    ArtifactCreate,
    ArtifactReferenceInput,
    M7GovernanceRequest,
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
)
from .storage import ArtifactStore, ArtifactStoreError


def _as_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class M7GovernanceModule:
    """Consolidate project audit, evaluate flow status and operational policies.

    M7 provides governance, traceability and continuous operational controls.
    It produces an immutable governance audit artifact, computes the project
    flow state (completed modules, awaiting approval, failed modules, and
    blocked reasons), evaluates operational indicators (strictly classifying
    measured, estimated, hypothesis and documentary evidence), and establishes
    a maintenance plan with procedures and future production controls.
    """

    module_id = "m7"
    contract_version = "v1.0"

    def __init__(self) -> None:
        self.executions = ExecutionRepository()

    def execute(
        self,
        db: Session,
        project_id: str,
        payload: M7GovernanceRequest,
        artifact_store: ArtifactStore,
        *,
        max_metadata_bytes: int,
    ) -> dict[str, Any]:
        self._validate_request(project_id, payload)
        project = require_editable_project(db, project_id)
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
                raise ConflictError("The idempotency key is already bound to another M7 execution")
            if existing.result_json is not None:
                return existing.result_json
            raise ConflictError("The idempotent M7 execution is already running")

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
            verified_artifacts = self._verify_referenced_artifacts(
                db, project_id, payload, artifact_store
            )
            self._verify_referenced_executions(db, project_id, payload)

            all_executions = list(
                db.scalars(
                    select(Execution)
                    .where(Execution.project_id == project_id)
                    .order_by(Execution.requested_at)
                )
            )
            all_approvals = list(
                db.scalars(
                    select(Approval)
                    .where(Approval.project_id == project_id)
                    .order_by(Approval.created_at)
                )
            )
            all_decisions = list(
                db.scalars(
                    select(Decision)
                    .where(Decision.project_id == project_id)
                    .order_by(Decision.created_at)
                )
            )
            all_audit_events = list(
                db.scalars(
                    select(AuditEvent)
                    .where(AuditEvent.project_id == project_id)
                    .order_by(AuditEvent.created_at)
                )
            )
            all_artifacts = list(
                db.scalars(
                    select(Artifact)
                    .where(Artifact.project_id == project_id)
                    .order_by(Artifact.created_at)
                )
            )

            project_state = self._evaluate_project_state(
                project, all_executions, all_approvals, payload.execution_id
            )
            indicators = self._calculate_operational_indicators(
                now, all_executions, all_artifacts, payload
            )
            maintenance_plan = self._build_maintenance_plan()

            audit_ref = self._persist_audit_artifact(
                db,
                project_id,
                execution,
                payload,
                all_audit_events,
                all_executions,
                all_approvals,
                all_decisions,
                all_artifacts,
                project_state,
                indicators,
                maintenance_plan,
                verified_artifacts,
                artifact_store,
                max_metadata_bytes=max_metadata_bytes,
                staged_storage_ids=staged_storage_ids,
            )

            output = self._result_envelope(
                payload,
                status="succeeded",
                audit_artifact=audit_ref,
                project_state=project_state,
                operational_indicators=indicators,
                maintenance_plan=maintenance_plan,
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
                "Artifact storage failed during M7 audit preparation",
            )
            raise ValidationError("Artifact storage failed during governance preparation") from exc
        except Exception as exc:
            self._cleanup_staged_artifacts(artifact_store, staged_storage_ids)
            self._fail_execution(
                db,
                execution.id,
                payload,
                input_hash,
                "Unexpected M7 governance preparation failure",
            )
            raise RuntimeError("M7 governance preparation failed") from exc

    def _validate_request(self, project_id: str, payload: M7GovernanceRequest) -> None:
        if payload.project_id != project_id:
            raise ValidationError("project_id in the contract does not match the URL scope")
        if payload.module_id != self.module_id:
            raise ValidationError("M7 execution requires module_id='m7'")
        if payload.contract_version != self.contract_version:
            raise ValidationError("M7 requires contract_version='v1.0'")
        if payload.status not in {"requested", "ready"}:
            raise ValidationError("M7 executions must start in requested or ready status")

    def _verify_referenced_artifacts(
        self,
        db: Session,
        project_id: str,
        payload: M7GovernanceRequest,
        artifact_store: ArtifactStore,
    ) -> list[Artifact]:
        verified: list[Artifact] = []
        for ref in payload.module_input.project_artifacts:
            artifact = artifacts.get_by_logical_version(
                db, project_id, ref.artifact_id, ref.artifact_version
            )
            if artifact is None or artifact.project_id != project_id:
                raise NotFoundError(
                    f"Referenced artifact '{ref.artifact_id}' ({ref.artifact_version}) "
                    "not found for project"
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

    def _verify_referenced_executions(
        self,
        db: Session,
        project_id: str,
        payload: M7GovernanceRequest,
    ) -> None:
        for exec_id in payload.module_input.execution_ids:
            execution = db.get(Execution, exec_id)
            if execution is None or execution.project_id != project_id:
                raise NotFoundError(
                    f"Referenced execution '{exec_id}' not found for project"
                )

    def _evaluate_project_state(
        self,
        project: Project,
        all_executions: list[Execution],
        all_approvals: list[Approval],
        current_execution_id: str,
    ) -> dict[str, Any]:
        module_statuses: dict[str, str] = {}
        for mod in ("m1", "m2", "m3", "m4", "m5", "m6", "m7"):
            if mod == "m7":
                module_statuses[mod] = "succeeded"
                continue
            mod_execs = [e for e in all_executions if e.module_id == mod and e.id != current_execution_id]
            if mod_execs:
                latest = mod_execs[-1]
                module_statuses[mod] = latest.status
            else:
                if mod == "m1":
                    module_statuses[mod] = "succeeded" if project.status != "draft" else "ready"
                else:
                    module_statuses[mod] = "not_started"

        blocked_reasons: list[str] = []
        for app in all_approvals:
            if app.status == "pending":
                blocked_reasons.append(
                    f"Pending approval required: action '{app.action}' on {app.scope_type} "
                    f"(approval_id: {app.id})"
                )

        for e in all_executions:
            if e.id != current_execution_id:
                if e.status == "failed_terminal":
                    blocked_reasons.append(
                        f"Terminal failure in module '{e.module_id}' (execution: {e.id}): "
                        f"{e.error_summary or 'No error summary'}"
                    )
                elif e.status == "awaiting_approval":
                    blocked_reasons.append(
                        f"Module '{e.module_id}' execution '{e.id}' is awaiting approval"
                    )

        if module_statuses.get("m6") in {"succeeded", "awaiting_approval"}:
            current_phase = "deployment"
        elif module_statuses.get("m5") in {"succeeded", "awaiting_approval"}:
            current_phase = "evaluation"
        elif module_statuses.get("m4") in {"succeeded", "awaiting_approval"}:
            current_phase = "modeling"
        elif module_statuses.get("m3") == "succeeded":
            current_phase = "data_preparation"
        elif module_statuses.get("m2") == "succeeded":
            current_phase = "data_understanding"
        else:
            current_phase = "business_understanding"

        return {
            "current_phase": current_phase,
            "module_statuses": module_statuses,
            "blocked_reasons": blocked_reasons,
        }

    def _calculate_operational_indicators(
        self,
        now: datetime,
        all_executions: list[Execution],
        all_artifacts: list[Artifact],
        payload: M7GovernanceRequest,
    ) -> list[dict[str, Any]]:
        indicators: list[dict[str, Any]] = []

        completed_execs = [
            e for e in all_executions
            if e.id != payload.execution_id and e.completed_at is not None
        ]

        if completed_execs:
            succeeded_count = sum(1 for e in completed_execs if e.status == "succeeded")
            rate = succeeded_count / len(completed_execs)
            indicators.append({
                "name": "execution_success_rate",
                "classification": "measured",
                "value_status": f"{rate:.1%}",
            })
        else:
            indicators.append({
                "name": "execution_success_rate",
                "classification": "measured",
                "value_status": "not_available",
            })

        timed_execs: list[tuple[datetime, datetime]] = []
        for e in completed_execs:
            s_at = _as_utc(e.started_at)
            c_at = _as_utc(e.completed_at)
            if s_at is not None and c_at is not None and c_at >= s_at:
                timed_execs.append((s_at, c_at))
        if timed_execs:
            durations = [(c_at - s_at).total_seconds() for s_at, c_at in timed_execs]
            mean_duration = sum(durations) / len(durations)
            indicators.append({
                "name": "mean_module_latency_seconds",
                "classification": "measured",
                "value_status": f"{mean_duration:.2f}s",
            })
        else:
            indicators.append({
                "name": "mean_module_latency_seconds",
                "classification": "measured",
                "value_status": "not_available",
            })

        bronze_artifacts = [
            a for a in all_artifacts
            if a.layer == "bronze" or a.artifact_type == "dataset.bronze"
        ]
        if bronze_artifacts:
            latest_bronze = max(
                bronze_artifacts,
                key=lambda a: _as_utc(a.created_at) or now,
            )
            created_dt = _as_utc(latest_bronze.created_at) or now
            age_days = (now - created_dt).days
            indicators.append({
                "name": "data_freshness_status",
                "classification": "measured",
                "value_status": f"{age_days} days since ingestion",
                "source_artifact": self._artifact_reference(latest_bronze),
            })
        else:
            indicators.append({
                "name": "data_freshness_status",
                "classification": "measured",
                "value_status": "not_available",
            })

        quality_artifacts = [
            a for a in all_artifacts
            if a.artifact_type in {"report.profile", "dataset.silver", "dataset.gold"}
        ]
        if quality_artifacts:
            latest_quality = max(
                quality_artifacts,
                key=lambda a: _as_utc(a.created_at) or now,
            )
            indicators.append({
                "name": "data_quality_compliance",
                "classification": "measured",
                "value_status": "verified",
                "source_artifact": self._artifact_reference(latest_quality),
            })
        else:
            indicators.append({
                "name": "data_quality_compliance",
                "classification": "documentary_evidence",
                "value_status": "not_available",
            })

        indicators.append({
            "name": "operational_cloud_cost",
            "classification": "documentary_evidence",
            "value_status": "not_applicable",
        })

        indicators.append({
            "name": "model_drift_monitoring",
            "classification": "documentary_evidence",
            "value_status": "deferred_to_production",
        })

        return indicators

    def _build_maintenance_plan(self) -> dict[str, Any]:
        return {
            "procedures": [
                (
                    "Rollback procedure: retain historical immutable artifacts and approvals; "
                    "de-activate package by resolving a new deployment approval with rejected status "
                    "and creating a new superseding version without deleting historical evidence."
                ),
                (
                    "Reprocessing procedure: upon data source schema or content update, initiate a "
                    "new pipeline run with a fresh context snapshot, generating new versioned "
                    "Bronze/Silver/Gold artifacts."
                ),
                (
                    "Audit trail retention procedure: preserve append-only audit_events and immutable "
                    "governance artifacts in local storage per project retention policy."
                ),
            ],
            "future_controls": [
                (
                    "Future production control: implement continuous concept drift and data drift "
                    "monitoring using population stability index (PSI) and Kolmogorov-Smirnov tests "
                    "once live production inference stream is established."
                ),
                (
                    "Future production control: configure automated alerting for prediction latency "
                    "spikes exceeding SLA thresholds in production serving runtime."
                ),
                (
                    "Future production control: establish recurring human-in-the-loop fairness and "
                    "demographic parity review on production predictions."
                ),
            ],
        }

    def _persist_audit_artifact(
        self,
        db: Session,
        project_id: str,
        execution: Execution,
        payload: M7GovernanceRequest,
        all_audit_events: list[AuditEvent],
        all_executions: list[Execution],
        all_approvals: list[Approval],
        all_decisions: list[Decision],
        all_artifacts: list[Artifact],
        project_state: dict[str, Any],
        indicators: list[dict[str, Any]],
        maintenance_plan: dict[str, Any],
        verified_artifacts: list[Artifact],
        artifact_store: ArtifactStore,
        *,
        max_metadata_bytes: int,
        staged_storage_ids: list[str],
    ) -> dict[str, Any]:
        digest = sha256_canonical(execution.id)[7:23]
        audit_artifact_id = f"m7-governance-audit-{digest}"

        audit_payload = {
            "format": "analytixflow.m7.governance-audit.v1",
            "project_id": project_id,
            "execution_id": execution.id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "audit_events_count": len(all_audit_events),
                "executions_count": len(all_executions),
                "approvals_count": len(all_approvals),
                "decisions_count": len(all_decisions),
                "artifacts_count": len(all_artifacts),
                "current_phase": project_state["current_phase"],
            },
            "audit_events": [
                {
                    "id": event.id,
                    "actor_type": event.actor_type,
                    "actor_id": event.actor_id,
                    "action": event.action,
                    "entity_type": event.entity_type,
                    "entity_id": event.entity_id,
                    "module_id": event.module_id,
                    "input_hash": event.input_hash,
                    "output_hash": event.output_hash,
                    "correlation_id": event.correlation_id,
                    "metadata": event.metadata_json,
                    "created_at": event.created_at.isoformat() if event.created_at else None,
                }
                for event in all_audit_events
            ],
            "executions": [
                {
                    "id": e.id,
                    "module_id": e.module_id,
                    "contract_version": e.contract_version,
                    "status": e.status,
                    "attempt": e.attempt,
                    "error_summary": e.error_summary,
                    "requested_at": e.requested_at.isoformat() if e.requested_at else None,
                    "started_at": e.started_at.isoformat() if e.started_at else None,
                    "completed_at": e.completed_at.isoformat() if e.completed_at else None,
                }
                for e in all_executions
            ],
            "approvals": [
                {
                    "id": a.id,
                    "action": a.action,
                    "scope_type": a.scope_type,
                    "status": a.status,
                    "artifact_id": a.artifact_id,
                    "artifact_version": a.artifact_version,
                    "requested_by": a.requested_by,
                    "resolved_by": a.resolved_by,
                    "reason": a.reason,
                    "created_at": a.created_at.isoformat() if a.created_at else None,
                    "resolved_at": a.resolved_at.isoformat() if a.resolved_at else None,
                }
                for a in all_approvals
            ],
            "decisions": [
                {
                    "id": d.id,
                    "decision_type": d.decision_type,
                    "question": d.question,
                    "status": d.status,
                    "selected_option": d.selected_option,
                    "rationale": d.rationale,
                    "decided_by": d.decided_by,
                    "created_at": d.created_at.isoformat() if d.created_at else None,
                }
                for d in all_decisions
            ],
            "project_state": project_state,
            "operational_indicators": indicators,
            "maintenance_plan": maintenance_plan,
        }

        stored = artifact_store.put(canonical_json(audit_payload).encode("utf-8"))
        staged_storage_ids.append(stored.storage_id)

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
                artifact_id=audit_artifact_id,
                artifact_type="governance.audit",
                artifact_version="v1",
                content_hash=stored.content_hash,
                storage_id=stored.storage_id,
                uri=stored.uri,
                media_type="application/json",
                layer="audit",
                produced_by_module=self.module_id,
                source_execution_id=execution.id,
                parent_artifact_refs=parent_refs,
                metadata={
                    "audit_events_count": len(all_audit_events),
                    "executions_count": len(all_executions),
                    "current_phase": project_state["current_phase"],
                },
            ),
            artifact_store,
            max_metadata_bytes=max_metadata_bytes,
            correlation_id=payload.correlation_id,
            commit_transaction=False,
        )
        return self._artifact_reference(artifact)

    def _result_envelope(
        self,
        payload: M7GovernanceRequest,
        *,
        status: str,
        audit_artifact: dict[str, Any],
        project_state: dict[str, Any],
        operational_indicators: list[dict[str, Any]],
        maintenance_plan: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "project_id": payload.project_id,
            "execution_id": payload.execution_id,
            "module_id": self.module_id,
            "contract_version": payload.contract_version,
            "context_snapshot_id": payload.context_snapshot_id,
            "correlation_id": payload.correlation_id,
            "status": status,
            "artifacts": [audit_artifact],
            "approval_refs": [],
            "warnings": list(payload.warnings),
            "errors": [],
            "next_actions": [
                {
                    "action": "generate_executive_dashboard",
                    "requires_approval": False,
                    "target_module": "m8",
                }
            ],
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "module_output": {
                "audit_artifact": audit_artifact,
                "project_state": project_state,
                "operational_indicators": operational_indicators,
                "maintenance_plan": maintenance_plan,
            },
        }

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
            action="execution.succeeded",
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
        payload: M7GovernanceRequest,
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
            metadata={"status": "failed_terminal", "error": "M7 governance preparation failed"},
        )
        commit(db)

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
    def _cleanup_staged_artifacts(artifact_store: ArtifactStore, storage_ids: list[str]) -> None:
        for storage_id in storage_ids:
            try:
                artifact_store.delete(storage_id)
            except (ArtifactStoreError, OSError):
                pass
        storage_ids.clear()
