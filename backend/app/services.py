from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .db.models import (
    Approval,
    Artifact,
    ArtifactLineage,
    AuditEvent,
    Decision,
    DecisionArtifactEvidence,
    Project,
    ProjectContextSnapshot,
)
from .domain.hashing import canonical_json, sha256_canonical
from .domain.sanitization import redact_sensitive
from .repositories import (
    ApprovalRepository,
    ArtifactRepository,
    AuditRepository,
    ContextSnapshotRepository,
    DecisionRepository,
    ProjectRepository,
)
from .storage import (
    ArtifactIntegrityError,
    ArtifactNotFoundError,
    ArtifactStorePathError,
    ArtifactStore,
    StoredArtifact,
)


class NotFoundError(Exception):
    pass


class ConflictError(Exception):
    pass


class ValidationError(Exception):
    pass


projects = ProjectRepository()
contexts = ContextSnapshotRepository()
artifacts = ArtifactRepository()
decisions = DecisionRepository()
approvals = ApprovalRepository()
audit = AuditRepository()


APPROVAL_SCOPE_BY_ACTION = {
    "select_alternative": "project",
    "request_iteration": "project",
    "record_insufficient_evidence": "project",
    "approve_ingestion_interpretation": "artifact",
    "approve_transformations": "artifact",
    "select_model_candidate": "artifact",
    "accept_model": "artifact",
    "approve_deployment_action": "artifact",
    "approve_test_artifact": "artifact",
}


def require_project(db: Session, project_id: str) -> Project:
    project = projects.get(db, project_id)
    if project is None:
        raise NotFoundError("Project not found")
    return project


def commit(db: Session) -> None:
    db.commit()


def record_audit(
    db: Session,
    *,
    project_id: str,
    action: str,
    entity_type: str,
    entity_id: str,
    actor_type: str = "user",
    actor_id: str | None = None,
    module_id: str | None = None,
    input_hash: str | None = None,
    output_hash: str | None = None,
    correlation_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> AuditEvent:
    event = AuditEvent(
        project_id=project_id,
        actor_type=actor_type,
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        module_id=module_id,
        input_hash=input_hash,
        output_hash=output_hash,
        correlation_id=correlation_id or str(uuid4()),
        metadata_json=redact_sensitive(metadata or {}),
    )
    audit.create(db, event)
    return event


def create_project(db: Session, payload, *, correlation_id: str | None = None) -> Project:
    project = Project(**payload.model_dump())
    projects.create(db, project)
    record_audit(
        db,
        project_id=project.id,
        action="project.created",
        entity_type="project",
        entity_id=project.id,
        actor_id=payload.owner_id,
        correlation_id=correlation_id,
        metadata={"company_name": payload.company_name},
    )
    commit(db)
    return project


def create_context_snapshot(
    db: Session, project_id: str, payload, *, correlation_id: str | None = None
) -> ProjectContextSnapshot:
    project = projects.get_for_update(db, project_id)
    if project is None:
        raise NotFoundError("Project not found")
    predecessor = contexts.latest(db, project_id)
    context_data = payload.context.model_dump(mode="json")
    snapshot = ProjectContextSnapshot(
        project_id=project_id,
        version=(predecessor.version + 1) if predecessor else 1,
        predecessor_id=predecessor.id if predecessor else None,
        context_data=context_data,
        content_hash=sha256_canonical(context_data),
        created_by=payload.created_by,
    )
    contexts.create(db, snapshot)
    record_audit(
        db,
        project_id=project_id,
        action="context.snapshot.created",
        entity_type="project_context_snapshot",
        entity_id=snapshot.id,
        actor_id=payload.created_by,
        correlation_id=correlation_id,
        input_hash=snapshot.content_hash,
        output_hash=snapshot.content_hash,
        metadata={"version": snapshot.version, "predecessor_id": snapshot.predecessor_id},
    )
    commit(db)
    return snapshot


def create_decision(db: Session, project_id: str, payload, *, correlation_id: str | None = None) -> Decision:
    require_project(db, project_id)
    if payload.selected_option is not None and payload.selected_option not in payload.options:
        raise ValidationError("selected_option must be one of options")
    if payload.status == "decided" and not payload.selected_option:
        raise ValidationError("A decided decision requires selected_option")
    if payload.status == "decided" and not payload.decided_by:
        raise ValidationError("A decided decision requires decided_by")
    evidence = _resolve_artifact_references(
        db,
        project_id,
        refs=payload.evidence_artifact_refs,
        legacy_ids=payload.evidence_artifact_ids,
    )
    decision = Decision(
        project_id=project_id,
        decision_type=payload.decision_type,
        question=payload.question,
        options=payload.options,
        selected_option=payload.selected_option,
        rationale=payload.rationale,
        evidence_artifact_ids=[item.logical_id for item in evidence],
        status=payload.status,
        decided_by=payload.decided_by,
        decided_at=None if payload.status == "pending" else _now(),
    )
    decisions.create(db, decision)
    for artifact in evidence:
        db.add(
            DecisionArtifactEvidence(
                project_id=project_id,
                decision_id=decision.id,
                artifact_id=artifact.id,
            )
        )
    db.flush()
    record_audit(
        db,
        project_id=project_id,
        action="decision.created",
        entity_type="decision",
        entity_id=decision.id,
        actor_id=payload.decided_by,
        correlation_id=correlation_id,
        input_hash=sha256_canonical(payload.model_dump(mode="json")),
        metadata={"decision_type": payload.decision_type, "status": payload.status},
    )
    commit(db)
    return decision


def create_artifact(
    db: Session,
    project_id: str,
    payload,
    artifact_store: ArtifactStore,
    *,
    max_metadata_bytes: int,
    correlation_id: str | None = None,
    commit_transaction: bool = True,
) -> Artifact:
    project = projects.get_for_update(db, project_id)
    if project is None:
        raise NotFoundError("Project not found")
    stored = _verified_storage(artifact_store, payload.storage_id, payload.content_hash)
    logical_id = payload.artifact_id or str(uuid4())
    if artifacts.get_by_logical_version(db, project_id, logical_id, payload.artifact_version) is not None:
        raise ConflictError("Artifact logical identifier and version already exist")
    version_number = _parse_artifact_version(payload.artifact_version)
    existing_versions = artifacts.list_by_logical_id(db, project_id, logical_id)
    predecessor = None
    if existing_versions:
        if any(item.legacy_version or item.version_number is None for item in existing_versions):
            raise ValidationError(
                "This logical artifact has legacy versions without an unambiguous predecessor chain"
            )
        predecessor = artifacts.latest_chain_version(db, project_id, logical_id)
        if predecessor is None or predecessor.version_number is None:
            raise ValidationError("The artifact predecessor chain is incomplete")
        expected_version = predecessor.version_number + 1
        if version_number != expected_version:
            raise ConflictError(
                f"The next version for this logical artifact must be v{expected_version}"
            )
    elif version_number != 1:
        raise ValidationError("The first version of a logical artifact must be v1")

    explicit_parents = _resolve_artifact_references(
        db,
        project_id,
        refs=payload.parent_artifact_refs,
        legacy_ids=payload.parent_artifact_ids,
    )
    same_identity_parents = [item for item in explicit_parents if item.logical_id == logical_id]
    if same_identity_parents:
        raise ValidationError("The predecessor is server-managed and cannot be supplied by the client")
    if predecessor is not None:
        if predecessor.id not in {item.id for item in explicit_parents}:
            explicit_parents.insert(0, predecessor)

    parent_artifacts = explicit_parents
    metadata = redact_sensitive(payload.metadata)
    if len(canonical_json(metadata).encode("utf-8")) > max_metadata_bytes:
        raise ValidationError("Artifact metadata exceeds the configured limit")
    artifact = Artifact(
        project_id=project_id,
        logical_id=logical_id,
        artifact_type=payload.artifact_type,
        artifact_version=payload.artifact_version,
        version_number=version_number,
        legacy_version=False,
        predecessor_artifact_id=predecessor.id if predecessor else None,
        predecessor_version_number=predecessor.version_number if predecessor else None,
        content_hash=stored.content_hash,
        storage_id=stored.storage_id,
        uri=stored.uri,
        media_type=payload.media_type,
        layer=payload.layer,
        produced_by_module=payload.produced_by_module,
        source_execution_id=payload.source_execution_id,
        parent_artifact_ids=[item.logical_id for item in parent_artifacts],
        metadata_json=metadata,
    )
    try:
        artifacts.create(db, artifact)
        for parent in parent_artifacts:
            db.add(
                ArtifactLineage(
                    project_id=project_id,
                    child_artifact_id=artifact.id,
                    parent_artifact_id=parent.id,
                )
            )
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError("Artifact version chain conflicts with an existing database record") from exc
    record_audit(
        db,
        project_id=project_id,
        action="artifact.created",
        entity_type="artifact",
        entity_id=artifact.id,
        actor_id=payload.produced_by_module,
        correlation_id=correlation_id,
        output_hash=artifact.content_hash,
        metadata={
            "artifact_id": artifact.logical_id,
            "artifact_version": artifact.artifact_version,
            "version_number": artifact.version_number,
            "predecessor_version_id": artifact.predecessor_artifact_id,
            "storage_id": artifact.storage_id,
        },
    )
    if commit_transaction:
        commit(db)
    return artifact


def create_approval(
    db: Session,
    project_id: str,
    payload,
    *,
    correlation_id: str | None = None,
    commit_transaction: bool = True,
) -> Approval:
    require_project(db, project_id)
    scope_type = payload.scope_type or _infer_scope_type(payload)
    expected_scope_type = APPROVAL_SCOPE_BY_ACTION.get(payload.action)
    if expected_scope_type is not None and scope_type != expected_scope_type:
        raise ValidationError(f"Action {payload.action} requires a {expected_scope_type} scope")

    artifact = None
    if payload.artifact_id is not None:
        if payload.artifact_version is None:
            raise ValidationError("artifact_version is required with artifact_id")
        artifact = artifacts.get_by_logical_version(
            db, project_id, payload.artifact_id, payload.artifact_version
        )
        if artifact is None:
            raise NotFoundError("Artifact version not found for project")
    elif payload.artifact_version is not None:
        raise ValidationError("artifact_id is required with artifact_version")

    if scope_type == "project" and (artifact is not None or payload.execution_id or payload.decision_id):
        raise ValidationError("Project approvals cannot contain artifact, execution or decision references")
    if scope_type == "artifact" and artifact is None:
        raise ValidationError("Artifact approvals require an exact artifact version")
    if scope_type == "execution" and not payload.execution_id:
        raise ValidationError("Execution approvals require execution_id")

    decision = None
    if payload.decision_id is not None:
        decision = db.get(Decision, payload.decision_id)
        if decision is None or decision.project_id != project_id:
            raise NotFoundError("Decision not found for project")

    scope_payload = {
        "project_id": project_id,
        "action": payload.action,
        "scope_type": scope_type,
        "artifact": (
            {
                "artifact_id": artifact.logical_id,
                "artifact_version": artifact.artifact_version,
                "content_hash": artifact.content_hash,
            }
            if artifact
            else None
        ),
        "execution_id": payload.execution_id,
        "decision_id": decision.id if decision else None,
    }
    scope_hash = sha256_canonical(scope_payload)
    if payload.scope_hash is not None and payload.scope_hash != scope_hash:
        raise ValidationError("scope_hash does not match the canonical approval scope")

    approval = Approval(
        project_id=project_id,
        action=payload.action,
        scope_type=scope_type,
        status="pending",
        artifact_id=artifact.id if artifact else None,
        artifact_version=artifact.artifact_version if artifact else None,
        execution_id=payload.execution_id,
        decision_id=decision.id if decision else None,
        scope_hash=scope_hash,
        requested_by=payload.requested_by,
        reason=payload.reason,
    )
    approvals.create(db, approval)
    record_audit(
        db,
        project_id=project_id,
        action="approval.created",
        entity_type="approval",
        entity_id=approval.id,
        actor_id=payload.requested_by,
        correlation_id=correlation_id,
        input_hash=approval.scope_hash,
        metadata={"action": approval.action, "scope_type": approval.scope_type},
    )
    if commit_transaction:
        commit(db)
    return approval


def resolve_approval(
    db: Session, project_id: str, approval_id: str, payload, *, correlation_id: str | None = None
) -> Approval:
    require_project(db, project_id)
    approval = approvals.get_for_update(db, approval_id)
    if approval is None or approval.project_id != project_id:
        raise NotFoundError("Approval not found for project")
    if approval.status != "pending":
        raise ConflictError("Resolved approvals cannot be reused")
    approval.status = payload.status
    approval.resolved_by = payload.resolved_by
    approval.reason = payload.reason or approval.reason
    approval.resolved_at = _now()
    record_audit(
        db,
        project_id=project_id,
        action="approval.resolved",
        entity_type="approval",
        entity_id=approval.id,
        actor_id=payload.resolved_by,
        correlation_id=correlation_id,
        input_hash=approval.scope_hash,
        metadata={"status": payload.status, "scope_type": approval.scope_type},
    )
    commit(db)
    return approval


def _verified_storage(
    artifact_store: ArtifactStore, storage_id: str | None, expected_hash: str | None
) -> StoredArtifact:
    if not storage_id:
        raise ValidationError("storage_id is required; artifact bytes must be stored server-side")
    try:
        stored = artifact_store.metadata(storage_id)
        artifact_store.read(storage_id, expected_hash=expected_hash)
    except ArtifactNotFoundError as exc:
        raise NotFoundError("Stored artifact not found") from exc
    except (ArtifactIntegrityError, ArtifactStorePathError) as exc:
        raise ValidationError("Stored artifact integrity validation failed") from exc
    return stored


def _resolve_artifact_references(
    db: Session,
    project_id: str,
    *,
    refs: list[Any],
    legacy_ids: list[str],
) -> list[Artifact]:
    if refs and legacy_ids:
        raise ValidationError("Use artifact references or legacy artifact ids, not both")
    resolved: list[Artifact] = []
    if refs:
        for ref in refs:
            artifact = artifacts.get_by_logical_version(db, project_id, ref.artifact_id, ref.artifact_version)
            if artifact is None:
                raise NotFoundError("Artifact version not found for project")
            resolved.append(artifact)
    else:
        for logical_id in legacy_ids:
            candidates = artifacts.list_by_logical_id(db, project_id, logical_id)
            if not candidates:
                raise NotFoundError("Artifact not found for project")
            if len(candidates) > 1:
                raise ValidationError("Artifact version is required for a versioned reference")
            resolved.append(candidates[0])
    if len({item.id for item in resolved}) != len(resolved):
        raise ValidationError("Artifact references must be unique")
    return resolved


def _parse_artifact_version(value: str) -> int:
    if not value.startswith("v") or not value[1:].isdigit():
        raise ValidationError("Artifact versions must use the vN format")
    version_number = int(value[1:])
    if version_number < 1:
        raise ValidationError("Artifact version must be greater than zero")
    return version_number


def _infer_scope_type(payload) -> str:
    if payload.artifact_id:
        return "artifact"
    if payload.execution_id:
        return "execution"
    return "project"


def _now() -> datetime:
    return datetime.now(timezone.utc)
