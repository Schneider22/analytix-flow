from __future__ import annotations

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from .db.models import Approval, Artifact, AuditEvent, Decision, Execution, Project, ProjectContextSnapshot


class ProjectRepository:
    def create(self, db: Session, project: Project) -> Project:
        db.add(project)
        db.flush()
        return project

    def get(self, db: Session, project_id: str) -> Project | None:
        return db.get(Project, project_id)

    def get_for_update(self, db: Session, project_id: str) -> Project | None:
        return db.scalar(select(Project).where(Project.id == project_id).with_for_update())

    def list(self, db: Session, *, limit: int, offset: int) -> list[Project]:
        return list(
            db.scalars(
                select(Project).order_by(desc(Project.created_at)).limit(limit).offset(offset)
            )
        )


class ContextSnapshotRepository:
    def next_version(self, db: Session, project_id: str) -> int:
        db.scalar(select(Project).where(Project.id == project_id).with_for_update())
        current = db.scalar(
            select(func.max(ProjectContextSnapshot.version)).where(
                ProjectContextSnapshot.project_id == project_id
            )
        )
        return (current or 0) + 1

    def latest(self, db: Session, project_id: str) -> ProjectContextSnapshot | None:
        return db.scalar(
            select(ProjectContextSnapshot)
            .where(ProjectContextSnapshot.project_id == project_id)
            .order_by(desc(ProjectContextSnapshot.version))
            .limit(1)
        )

    def create(self, db: Session, snapshot: ProjectContextSnapshot) -> ProjectContextSnapshot:
        db.add(snapshot)
        db.flush()
        return snapshot

    def list(self, db: Session, project_id: str) -> list[ProjectContextSnapshot]:
        return list(
            db.scalars(
                select(ProjectContextSnapshot)
                .where(ProjectContextSnapshot.project_id == project_id)
                .order_by(ProjectContextSnapshot.version)
            )
        )


class ExecutionRepository:
    def get(self, db: Session, execution_id: str) -> Execution | None:
        return db.get(Execution, execution_id)

    def get_by_idempotency(
        self, db: Session, project_id: str, module_id: str, idempotency_key: str
    ) -> Execution | None:
        return db.scalar(
            select(Execution).where(
                Execution.project_id == project_id,
                Execution.module_id == module_id,
                Execution.idempotency_key == idempotency_key,
            )
        )

    def create(self, db: Session, execution: Execution) -> Execution:
        db.add(execution)
        db.flush()
        return execution


class ArtifactRepository:
    def get(self, db: Session, artifact_id: str) -> Artifact | None:
        return db.get(Artifact, artifact_id)

    def get_by_logical_version(
        self, db: Session, project_id: str, logical_id: str, artifact_version: str
    ) -> Artifact | None:
        return db.scalar(
            select(Artifact).where(
                Artifact.project_id == project_id,
                Artifact.logical_id == logical_id,
                Artifact.artifact_version == artifact_version,
            )
        )

    def list_by_logical_id(self, db: Session, project_id: str, logical_id: str) -> list[Artifact]:
        return list(
            db.scalars(
                select(Artifact)
                .where(Artifact.project_id == project_id, Artifact.logical_id == logical_id)
                .order_by(Artifact.version_number.desc().nullslast(), desc(Artifact.created_at))
            )
        )

    def latest_chain_version(self, db: Session, project_id: str, logical_id: str) -> Artifact | None:
        return db.scalar(
            select(Artifact)
            .where(
                Artifact.project_id == project_id,
                Artifact.logical_id == logical_id,
                Artifact.legacy_version.is_(False),
            )
            .order_by(desc(Artifact.version_number))
            .limit(1)
            .with_for_update()
        )

    def create(self, db: Session, artifact: Artifact) -> Artifact:
        db.add(artifact)
        db.flush()
        return artifact

    def list(self, db: Session, project_id: str) -> list[Artifact]:
        return list(
            db.scalars(
                select(Artifact)
                .where(Artifact.project_id == project_id)
                .order_by(Artifact.logical_id, Artifact.artifact_version)
            )
        )


class DecisionRepository:
    def create(self, db: Session, decision: Decision) -> Decision:
        db.add(decision)
        db.flush()
        return decision

    def list(self, db: Session, project_id: str) -> list[Decision]:
        return list(
            db.scalars(
                select(Decision)
                .where(Decision.project_id == project_id)
                .order_by(desc(Decision.created_at))
            )
        )


class ApprovalRepository:
    def get(self, db: Session, approval_id: str) -> Approval | None:
        return db.get(Approval, approval_id)

    def get_for_update(self, db: Session, approval_id: str) -> Approval | None:
        return db.scalar(select(Approval).where(Approval.id == approval_id).with_for_update())

    def create(self, db: Session, approval: Approval) -> Approval:
        db.add(approval)
        db.flush()
        return approval

    def list(self, db: Session, project_id: str) -> list[Approval]:
        return list(
            db.scalars(
                select(Approval)
                .where(Approval.project_id == project_id)
                .order_by(desc(Approval.created_at))
            )
        )


class AuditRepository:
    def create(self, db: Session, event: AuditEvent) -> AuditEvent:
        db.add(event)
        db.flush()
        return event

    def list(self, db: Session, project_id: str) -> list[AuditEvent]:
        return list(
            db.scalars(
                select(AuditEvent)
                .where(AuditEvent.project_id == project_id)
                .order_by(desc(AuditEvent.created_at))
            )
        )
