from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    JSON,
    String,
    UniqueConstraint,
    event,
    inspect,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


def new_id() -> str:
    return str(uuid4())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    owner_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    company_description: Mapped[str] = mapped_column(String, nullable=False)
    business_need: Mapped[str] = mapped_column(String, nullable=False)
    expected_objective: Mapped[str] = mapped_column(String, nullable=False)
    business_rules: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    constraints: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    success_criteria: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="draft")
    current_phase: Mapped[str] = mapped_column(String(64), nullable=False, default="business_understanding")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    context_snapshots: Mapped[list[ProjectContextSnapshot]] = relationship(
        back_populates="project", order_by="ProjectContextSnapshot.version"
    )
    artifacts: Mapped[list[Artifact]] = relationship(back_populates="project")
    decisions: Mapped[list[Decision]] = relationship(back_populates="project")
    approvals: Mapped[list[Approval]] = relationship(back_populates="project")
    audit_events: Mapped[list[AuditEvent]] = relationship(back_populates="project")


class ProjectContextSnapshot(Base):
    __tablename__ = "project_context_snapshots"
    __table_args__ = (UniqueConstraint("project_id", "version", name="uq_context_project_version"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(nullable=False)
    predecessor_id: Mapped[str | None] = mapped_column(
        ForeignKey("project_context_snapshots.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    context_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(71), nullable=False)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    project: Mapped[Project] = relationship(back_populates="context_snapshots")
    predecessor: Mapped[ProjectContextSnapshot | None] = relationship(
        "ProjectContextSnapshot", remote_side="ProjectContextSnapshot.id", back_populates="successors"
    )
    successors: Mapped[list[ProjectContextSnapshot]] = relationship(
        "ProjectContextSnapshot", back_populates="predecessor"
    )


class Artifact(Base):
    __tablename__ = "artifacts"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "logical_id", "artifact_version", name="uq_artifact_project_logical_version"
        ),
        UniqueConstraint(
            "id", "project_id", "logical_id", "version_number",
            name="uq_artifact_identity_version_number",
        ),
        UniqueConstraint(
            "project_id", "logical_id", "version_number",
            name="uq_artifact_project_logical_version_number",
        ),
        ForeignKeyConstraint(
            ["predecessor_artifact_id", "project_id", "logical_id", "predecessor_version_number"],
            ["artifacts.id", "artifacts.project_id", "artifacts.logical_id", "artifacts.version_number"],
            name="fk_artifact_predecessor_same_identity",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "(legacy_version IS TRUE AND version_number IS NULL AND predecessor_artifact_id IS NULL "
            "AND predecessor_version_number IS NULL) "
            "OR (legacy_version IS FALSE AND version_number IS NOT NULL AND version_number = 1 "
            "AND predecessor_artifact_id IS NULL AND predecessor_version_number IS NULL) "
            "OR (legacy_version IS FALSE AND version_number IS NOT NULL AND version_number > 1 "
            "AND predecessor_artifact_id IS NOT NULL AND predecessor_version_number = version_number - 1)",
            name="ck_artifact_version_chain_shape",
        ),
        CheckConstraint(
            "legacy_version IS TRUE OR artifact_version = ('v' || CAST(version_number AS VARCHAR))",
            name="ck_artifact_version_label_matches_number",
        ),
        CheckConstraint(
            "predecessor_artifact_id IS NULL OR predecessor_artifact_id <> id",
            name="ck_artifact_predecessor_not_self",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False, index=True)
    logical_id: Mapped[str] = mapped_column(String(128), nullable=False)
    artifact_type: Mapped[str] = mapped_column(String(128), nullable=False)
    artifact_version: Mapped[str] = mapped_column(String(32), nullable=False)
    version_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    legacy_version: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    predecessor_artifact_id: Mapped[str | None] = mapped_column(
        ForeignKey("artifacts.id", name="fk_artifact_predecessor_id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    predecessor_version_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content_hash: Mapped[str] = mapped_column(String(71), nullable=False)
    uri: Mapped[str | None] = mapped_column(String, nullable=True)
    media_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    layer: Mapped[str | None] = mapped_column(String(32), nullable=True)
    produced_by_module: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_execution_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    storage_id: Mapped[str | None] = mapped_column(String(36), nullable=True, unique=True)
    parent_artifact_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    project: Mapped[Project] = relationship(back_populates="artifacts")
    parent_links: Mapped[list[ArtifactLineage]] = relationship(
        "ArtifactLineage",
        foreign_keys="ArtifactLineage.child_artifact_id",
        back_populates="child",
        cascade="all, delete-orphan",
    )
    derived_links: Mapped[list[ArtifactLineage]] = relationship(
        "ArtifactLineage",
        foreign_keys="ArtifactLineage.parent_artifact_id",
        back_populates="parent",
    )
    predecessor: Mapped[Artifact | None] = relationship(
        "Artifact",
        foreign_keys="Artifact.predecessor_artifact_id",
        remote_side="Artifact.id",
        back_populates="successors",
    )
    successors: Mapped[list[Artifact]] = relationship(
        "Artifact",
        foreign_keys="Artifact.predecessor_artifact_id",
        back_populates="predecessor",
    )


class ArtifactLineage(Base):
    __tablename__ = "artifact_lineage"
    __table_args__ = (
        UniqueConstraint("child_artifact_id", "parent_artifact_id", name="uq_artifact_lineage_pair"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    child_artifact_id: Mapped[str] = mapped_column(
        ForeignKey("artifacts.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    parent_artifact_id: Mapped[str] = mapped_column(
        ForeignKey("artifacts.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    child: Mapped[Artifact] = relationship(
        "Artifact", foreign_keys=[child_artifact_id], back_populates="parent_links"
    )
    parent: Mapped[Artifact] = relationship(
        "Artifact", foreign_keys=[parent_artifact_id], back_populates="derived_links"
    )


class Decision(Base):
    __tablename__ = "decisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False, index=True)
    decision_type: Mapped[str] = mapped_column(String(128), nullable=False)
    question: Mapped[str] = mapped_column(String, nullable=False)
    options: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    selected_option: Mapped[str | None] = mapped_column(String, nullable=True)
    rationale: Mapped[str | None] = mapped_column(String, nullable=True)
    evidence_artifact_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    decided_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    project: Mapped[Project] = relationship(back_populates="decisions")
    evidence_links: Mapped[list[DecisionArtifactEvidence]] = relationship(
        "DecisionArtifactEvidence", back_populates="decision", cascade="all, delete-orphan"
    )


class DecisionArtifactEvidence(Base):
    __tablename__ = "decision_artifact_evidence"
    __table_args__ = (
        UniqueConstraint("decision_id", "artifact_id", name="uq_decision_artifact_evidence_pair"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    decision_id: Mapped[str] = mapped_column(
        ForeignKey("decisions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    artifact_id: Mapped[str] = mapped_column(
        ForeignKey("artifacts.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    decision: Mapped[Decision] = relationship("Decision", back_populates="evidence_links")
    artifact: Mapped[Artifact] = relationship("Artifact")


class Approval(Base):
    __tablename__ = "approvals"
    __table_args__ = (
        CheckConstraint(
            "(scope_type = 'project' AND artifact_id IS NULL AND artifact_version IS NULL AND execution_id IS NULL) "
            "OR (scope_type = 'artifact' AND artifact_id IS NOT NULL AND artifact_version IS NOT NULL) "
            "OR (scope_type = 'execution' AND execution_id IS NOT NULL)",
            name="ck_approval_scope_shape",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    scope_type: Mapped[str] = mapped_column(String(32), nullable=False, default="project")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    artifact_id: Mapped[str | None] = mapped_column(ForeignKey("artifacts.id", ondelete="RESTRICT"), nullable=True)
    artifact_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    execution_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    decision_id: Mapped[str | None] = mapped_column(ForeignKey("decisions.id", ondelete="RESTRICT"), nullable=True)
    scope_hash: Mapped[str] = mapped_column(String(71), nullable=False)
    requested_by: Mapped[str] = mapped_column(String(128), nullable=False)
    resolved_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reason: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    project: Mapped[Project] = relationship(back_populates="approvals")
    artifact: Mapped[Artifact | None] = relationship("Artifact")
    decision: Mapped[Decision | None] = relationship("Decision")


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False, index=True)
    actor_type: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(128), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(128), nullable=False)
    module_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    input_hash: Mapped[str | None] = mapped_column(String(71), nullable=True)
    output_hash: Mapped[str | None] = mapped_column(String(71), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    project: Mapped[Project] = relationship(back_populates="audit_events")


@event.listens_for(Artifact.__table__, "after_create")
def create_artifact_immutability_guards(_table, connection, **_kwargs):
    if connection.dialect.name == "sqlite":
        connection.exec_driver_sql(
            "CREATE TRIGGER IF NOT EXISTS trg_artifacts_immutable_update "
            "BEFORE UPDATE ON artifacts BEGIN "
            "SELECT RAISE(ABORT, 'Artifact versions are immutable'); END"
        )
        connection.exec_driver_sql(
            "CREATE TRIGGER IF NOT EXISTS trg_artifacts_immutable_delete "
            "BEFORE DELETE ON artifacts BEGIN "
            "SELECT RAISE(ABORT, 'Artifact versions are immutable'); END"
        )
    elif connection.dialect.name == "postgresql":
        connection.exec_driver_sql(
            "CREATE OR REPLACE FUNCTION analytixflow_reject_artifact_mutation() "
            "RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN "
            "RAISE EXCEPTION 'Artifact versions are immutable'; END; $$"
        )
        connection.exec_driver_sql(
            "DROP TRIGGER IF EXISTS trg_artifacts_immutable ON artifacts"
        )
        connection.exec_driver_sql(
            "CREATE TRIGGER trg_artifacts_immutable "
            "BEFORE UPDATE OR DELETE ON artifacts FOR EACH ROW "
            "EXECUTE FUNCTION analytixflow_reject_artifact_mutation()"
        )


@event.listens_for(Artifact.__table__, "after_drop")
def drop_artifact_immutability_guards(_table, connection, **_kwargs):
    if connection.dialect.name == "sqlite":
        connection.exec_driver_sql("DROP TRIGGER IF EXISTS trg_artifacts_immutable_update")
        connection.exec_driver_sql("DROP TRIGGER IF EXISTS trg_artifacts_immutable_delete")
    elif connection.dialect.name == "postgresql":
        connection.exec_driver_sql("DROP FUNCTION IF EXISTS analytixflow_reject_artifact_mutation()")


@event.listens_for(ProjectContextSnapshot, "before_update")
@event.listens_for(ProjectContextSnapshot, "before_delete")
@event.listens_for(AuditEvent, "before_update")
@event.listens_for(AuditEvent, "before_delete")
def prevent_immutable_mutation(_mapper, _connection, _target):
    raise ValueError("Immutable records cannot be updated or deleted")


@event.listens_for(Artifact, "before_update")
@event.listens_for(Artifact, "before_delete")
@event.listens_for(Decision, "before_update")
@event.listens_for(Decision, "before_delete")
@event.listens_for(Approval, "before_delete")
def prevent_versioned_record_mutation(_mapper, _connection, _target):
    raise ValueError("Versioned records cannot be updated or deleted")


@event.listens_for(Approval, "before_update")
def prevent_approval_scope_mutation(mapper, _connection, target):
    state = inspect(target)
    immutable_fields = (
        "project_id",
        "action",
        "scope_type",
        "artifact_id",
        "artifact_version",
        "execution_id",
        "decision_id",
        "scope_hash",
        "requested_by",
        "created_at",
    )
    if any(state.attrs[field].history.has_changes() for field in immutable_fields):
        raise ValueError("Approval scope cannot be changed after creation")


@event.listens_for(Project, "before_delete")
def prevent_project_deletion(_mapper, _connection, _target):
    raise ValueError("Projects cannot be deleted; archive them instead")
