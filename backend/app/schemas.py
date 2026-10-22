from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class ProjectCreate(StrictModel):
    organization_id: str | None = None
    owner_id: str | None = None
    company_name: str = Field(min_length=1, max_length=255)
    company_description: str = Field(min_length=1, max_length=10000)
    business_need: str = Field(min_length=1, max_length=10000)
    expected_objective: str = Field(min_length=1, max_length=10000)
    business_rules: list[str] = Field(default_factory=list, max_length=100)
    constraints: list[str] = Field(default_factory=list, max_length=100)
    success_criteria: list[str] = Field(min_length=1, max_length=100)


class ProjectRead(ProjectCreate):
    id: str
    status: str
    current_phase: str
    created_at: datetime
    updated_at: datetime


class ContextPayload(StrictModel):
    company_name: str = Field(min_length=1)
    company_description: str = Field(min_length=1, max_length=10000)
    business_need: str = Field(min_length=1, max_length=10000)
    expected_objective: str = Field(min_length=1, max_length=10000)
    business_rules: list[str] = Field(default_factory=list, max_length=100)
    constraints: list[str] = Field(default_factory=list, max_length=100)
    assumptions: list[str] = Field(default_factory=list, max_length=100)
    success_criteria: list[str] = Field(min_length=1, max_length=100)


class ContextCreate(StrictModel):
    context: ContextPayload
    created_by: str = Field(min_length=1, max_length=128)


class ContextRead(StrictModel):
    id: str
    project_id: str
    version: int
    predecessor_id: str | None
    context: ContextPayload
    content_hash: str
    created_by: str
    created_at: datetime


class ArtifactReferenceInput(StrictModel):
    artifact_id: str = Field(min_length=1, max_length=128)
    artifact_version: str = Field(pattern=r"^v[1-9][0-9]*$")


class DecisionCreate(StrictModel):
    decision_type: str = Field(min_length=1, max_length=128)
    question: str = Field(min_length=1)
    options: list[str] = Field(min_length=1, max_length=50)
    selected_option: str | None = Field(default=None, max_length=255)
    rationale: str | None = Field(default=None, max_length=10000)
    evidence_artifact_ids: list[str] = Field(default_factory=list, max_length=100)
    evidence_artifact_refs: list[ArtifactReferenceInput] = Field(default_factory=list, max_length=100)
    status: Literal["pending", "decided", "rejected"] = "pending"
    decided_by: str | None = None

    @field_validator("selected_option")
    @classmethod
    def selected_option_not_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("selected_option cannot be blank")
        return value


class DecisionRead(DecisionCreate):
    id: str
    project_id: str
    decided_at: datetime | None
    created_at: datetime


class ArtifactCreate(StrictModel):
    artifact_id: str | None = Field(default=None, min_length=1, max_length=128)
    artifact_type: str = Field(min_length=1, max_length=128)
    artifact_version: str = Field(pattern=r"^v[1-9][0-9]*$")
    content_hash: str | None = Field(default=None, pattern=r"^sha256:[a-f0-9]{64}$")
    storage_id: str | None = None
    uri: str | None = Field(default=None, max_length=2048)
    media_type: str | None = Field(default=None, max_length=255)
    layer: str | None = Field(default=None, max_length=32)
    produced_by_module: str | None = Field(default=None, max_length=32)
    source_execution_id: str | None = Field(default=None, max_length=128)
    parent_artifact_ids: list[str] = Field(default_factory=list, max_length=100)
    parent_artifact_refs: list[ArtifactReferenceInput] = Field(default_factory=list, max_length=100)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ArtifactRead(ArtifactCreate):
    artifact_id: str
    project_id: str
    version_id: str
    artifact_version: str = Field(min_length=1, max_length=32)
    version_number: int | None
    legacy_version: bool
    predecessor_version_id: str | None
    predecessor_artifact_id: str | None
    storage_id: str | None
    content_hash: str
    uri: str
    created_at: datetime


class ApprovalCreate(StrictModel):
    action: str = Field(min_length=1, max_length=128)
    scope_type: Literal["project", "artifact", "execution"] | None = None
    artifact_id: str | None = Field(default=None, min_length=1, max_length=128)
    artifact_version: str | None = Field(default=None, pattern=r"^v[1-9][0-9]*$")
    execution_id: str | None = Field(default=None, min_length=1, max_length=128)
    decision_id: str | None = Field(default=None, min_length=1, max_length=36)
    scope_hash: str | None = Field(default=None, pattern=r"^sha256:[a-f0-9]{64}$")
    requested_by: str = Field(min_length=1, max_length=128)
    reason: str | None = Field(default=None, max_length=10000)


class ApprovalResolve(StrictModel):
    status: Literal["approved", "rejected"]
    resolved_by: str = Field(min_length=1, max_length=128)
    reason: str | None = None


class ApprovalRead(StrictModel):
    id: str
    project_id: str
    action: str
    scope_type: Literal["project", "artifact", "execution"]
    status: str
    artifact_id: str | None
    artifact_version: str | None
    execution_id: str | None
    decision_id: str | None
    scope_hash: str
    requested_by: str
    resolved_by: str | None
    reason: str | None
    created_at: datetime
    resolved_at: datetime | None


class AuditEventRead(StrictModel):
    id: str
    project_id: str
    actor_type: str
    actor_id: str | None
    action: str
    entity_type: str
    entity_id: str
    module_id: str | None
    input_hash: str | None
    output_hash: str | None
    correlation_id: str | None
    metadata: dict[str, Any]
    created_at: datetime


class HealthRead(StrictModel):
    status: Literal["ok", "degraded"]
    database: Literal["ok", "unavailable"]
