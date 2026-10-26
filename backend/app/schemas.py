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


class ContractArtifactReference(StrictModel):
    artifact_id: str = Field(min_length=1, max_length=128)
    artifact_type: str = Field(min_length=1, max_length=128)
    artifact_version: str = Field(pattern=r"^v[1-9][0-9]*$")
    version_number: int = Field(ge=1)
    version_id: str | None = Field(default=None, min_length=1)
    predecessor_version_id: str | None = Field(default=None, min_length=1)
    content_hash: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    uri: str | None = Field(default=None, min_length=1)
    media_type: str | None = Field(default=None, min_length=1)
    layer: Literal["source", "bronze", "silver", "gold", "model", "report", "deployment", "audit", "other"] | None = None
    produced_by_module: str | None = Field(default=None, min_length=1)
    created_at: datetime | None = None


class M2IngestionOption(StrictModel):
    artifact_id: str = Field(min_length=1, max_length=128)
    format: Literal["csv", "xlsx", "xls"]
    encoding: str | None = None
    delimiter: str | None = Field(default=None, min_length=1, max_length=1)
    sheet_name: str | None = None
    header_row: int | None = Field(default=None, ge=0)
    date_interpretation: str | None = None


class M2ModuleInput(StrictModel):
    selected_alternative_id: str = Field(min_length=1)
    source_artifacts: list[ContractArtifactReference] = Field(min_length=1)
    ingestion_options: list[M2IngestionOption] = Field(min_length=1)


class M2IngestionRequest(StrictModel):
    project_id: str = Field(min_length=1)
    execution_id: str = Field(min_length=1, max_length=128)
    module_id: Literal["m2"]
    contract_version: str = Field(pattern=r"^v[0-9]+(?:\.[0-9]+){0,2}$")
    context_snapshot_id: str = Field(min_length=1)
    artifact_refs: list[ContractArtifactReference] = Field(default_factory=list)
    status: Literal["requested", "ready", "running", "awaiting_approval", "succeeded", "rejected", "failed_retryable", "failed_terminal", "superseded"]
    warnings: list[str] = Field(default_factory=list)
    errors: list[dict[str, Any]] = Field(default_factory=list)
    correlation_id: str = Field(min_length=1, max_length=128)
    idempotency_key: str = Field(min_length=1, max_length=128)
    requested_by: str | None = Field(default=None, min_length=1, max_length=128)
    requested_at: datetime | None = None
    input_hash: str | None = Field(default=None, pattern=r"^sha256:[a-f0-9]{64}$")
    approval_refs: list[dict[str, Any]] = Field(default_factory=list)
    module_input: M2ModuleInput


class ContractApprovalReference(StrictModel):
    approval_id: str = Field(min_length=1, max_length=36)
    action: str = Field(min_length=1, max_length=128)
    scope_type: Literal["project", "artifact", "execution"]
    status: Literal["pending", "approved", "rejected", "revoked"]
    scope_hash: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    artifact_id: str | None = Field(default=None, min_length=1, max_length=128)
    artifact_version: str | None = Field(default=None, pattern=r"^v[1-9][0-9]*$")
    execution_id: str | None = Field(default=None, min_length=1, max_length=128)
    decision_id: str | None = Field(default=None, min_length=1, max_length=36)
    approved_by: str | None = Field(default=None, min_length=1, max_length=128)
    approved_at: datetime | None = None
    reason: str | None = Field(default=None, min_length=1)


class M3TransformationRule(StrictModel):
    rule_id: str = Field(min_length=1, max_length=128)
    action: Literal[
        "normalize_column_names",
        "drop_duplicate_rows",
        "fill_missing_values",
        "parse_date_columns",
        "drop_empty_rows",
    ]
    reason: str = Field(min_length=1, max_length=10000)
    approval_required: bool
    parameters: dict[str, Any] = Field(default_factory=dict)


class M3TransformationPlan(StrictModel):
    rules: list[M3TransformationRule] = Field(default_factory=list, max_length=100)


class M3QualityPolicy(StrictModel):
    required_checks: list[str] = Field(default_factory=list, max_length=100)
    blocking_conditions: list[str] = Field(default_factory=list, max_length=100)


class M3ModuleInput(StrictModel):
    bronze_artifacts: list[ContractArtifactReference] = Field(min_length=1, max_length=100)
    transformation_plan: M3TransformationPlan
    business_rules: list[str] = Field(default_factory=list, max_length=100)
    quality_policy: M3QualityPolicy


class M3PreparationRequest(StrictModel):
    project_id: str = Field(min_length=1)
    execution_id: str = Field(min_length=1, max_length=128)
    module_id: Literal["m3"]
    contract_version: Literal["v1.1"]
    context_snapshot_id: str = Field(min_length=1)
    artifact_refs: list[ContractArtifactReference] = Field(default_factory=list)
    status: Literal[
        "requested",
        "ready",
        "running",
        "awaiting_approval",
        "succeeded",
        "rejected",
        "failed_retryable",
        "failed_terminal",
        "superseded",
    ]
    warnings: list[str] = Field(default_factory=list)
    errors: list[dict[str, Any]] = Field(default_factory=list)
    correlation_id: str = Field(min_length=1, max_length=128)
    idempotency_key: str = Field(min_length=1, max_length=128)
    requested_by: str | None = Field(default=None, min_length=1, max_length=128)
    requested_at: datetime | None = None
    input_hash: str | None = Field(default=None, pattern=r"^sha256:[a-f0-9]{64}$")
    approval_refs: list[ContractApprovalReference] = Field(default_factory=list, max_length=100)
    module_input: M3ModuleInput


class M4ModelPolicy(StrictModel):
    problem_type: Literal["classification", "regression", "descriptive"]
    allowed_techniques: list[str] = Field(min_length=1, max_length=50)
    interpretability_constraints: list[str] = Field(default_factory=list, max_length=100)


class M4SplitPolicy(StrictModel):
    strategy: Literal["holdout", "cross_validation", "temporal_holdout"]
    test_fraction: float = Field(gt=0, lt=1)
    folds: int | None = Field(default=None, ge=2, le=100)
    time_column: str | None = Field(default=None, min_length=1, max_length=255)


class M4Reproducibility(StrictModel):
    random_seed: int
    record_environment: bool


class M4ModuleInput(StrictModel):
    gold_dataset: ContractArtifactReference
    problem_definition: ContractArtifactReference
    target_column: str | None = Field(default=None, min_length=1, max_length=255)
    model_policy: M4ModelPolicy
    split_policy: M4SplitPolicy
    reproducibility: M4Reproducibility


class M4ModelingRequest(StrictModel):
    project_id: str = Field(min_length=1)
    execution_id: str = Field(min_length=1, max_length=128)
    module_id: Literal["m4"]
    contract_version: str = Field(pattern=r"^v[0-9]+(?:\.[0-9]+){0,2}$")
    context_snapshot_id: str = Field(min_length=1)
    artifact_refs: list[ContractArtifactReference] = Field(default_factory=list)
    status: Literal[
        "requested",
        "ready",
        "running",
        "awaiting_approval",
        "succeeded",
        "rejected",
        "failed_retryable",
        "failed_terminal",
        "superseded",
    ]
    warnings: list[str] = Field(default_factory=list)
    errors: list[dict[str, Any]] = Field(default_factory=list)
    correlation_id: str = Field(min_length=1, max_length=128)
    idempotency_key: str = Field(min_length=1, max_length=128)
    requested_by: str | None = Field(default=None, min_length=1, max_length=128)
    requested_at: datetime | None = None
    input_hash: str | None = Field(default=None, pattern=r"^sha256:[a-f0-9]{64}$")
    approval_refs: list[ContractApprovalReference] = Field(default_factory=list, max_length=100)
    module_input: M4ModuleInput


class M5Baseline(StrictModel):
    description: str = Field(min_length=1, max_length=10000)
    artifact_or_method: str = Field(min_length=1, max_length=255)


class M5EvaluationPolicy(StrictModel):
    primary_metrics: list[str] = Field(min_length=1, max_length=50)
    secondary_metrics: list[str] = Field(default_factory=list, max_length=50)
    validation_strategy: Literal["holdout", "cross_validation", "temporal_holdout"]
    bias_checks: list[str] = Field(default_factory=list, max_length=50)


class M5ModuleInput(StrictModel):
    candidate_models: list[ContractArtifactReference] = Field(min_length=1, max_length=100)
    gold_dataset: ContractArtifactReference
    baseline: M5Baseline
    evaluation_policy: M5EvaluationPolicy
    success_criteria: list[str] = Field(min_length=1, max_length=100)


class M5EvaluationRequest(StrictModel):
    project_id: str = Field(min_length=1)
    execution_id: str = Field(min_length=1, max_length=128)
    module_id: Literal["m5"]
    contract_version: Literal["v1.0"]
    context_snapshot_id: str = Field(min_length=1)
    artifact_refs: list[ContractArtifactReference] = Field(default_factory=list, max_length=100)
    status: Literal[
        "requested",
        "ready",
        "running",
        "awaiting_approval",
        "succeeded",
        "rejected",
        "failed_retryable",
        "failed_terminal",
        "superseded",
    ]
    warnings: list[str] = Field(default_factory=list)
    errors: list[dict[str, Any]] = Field(default_factory=list)
    correlation_id: str = Field(min_length=1, max_length=128)
    idempotency_key: str = Field(min_length=1, max_length=128)
    requested_by: str | None = Field(default=None, min_length=1, max_length=128)
    requested_at: datetime | None = None
    input_hash: str | None = Field(default=None, pattern=r"^sha256:[a-f0-9]{64}$")
    approval_refs: list[ContractApprovalReference] = Field(min_length=1, max_length=100)
    module_input: M5ModuleInput


class M6DeploymentTarget(StrictModel):
    target_type: Literal["local_process", "docker_artifact", "cloud_plan_only"]
    cloud_execution_allowed: Literal[False]
    configuration: dict[str, Any] = Field(default_factory=dict)


class M6ApiContract(StrictModel):
    operation: str = Field(min_length=1)
    request_schema: dict[str, Any]
    response_schema: dict[str, Any]


class M6RuntimePolicy(StrictModel):
    network_access: Literal["denied", "approved_allowlist"]
    secret_access: Literal["none", "declared_runtime_secrets"]


class M6ModuleInput(StrictModel):
    selected_model: ContractArtifactReference
    deployment_target: M6DeploymentTarget
    api_contract: M6ApiContract
    runtime_policy: M6RuntimePolicy


class M6DeploymentRequest(StrictModel):
    project_id: str = Field(min_length=1)
    execution_id: str = Field(min_length=1, max_length=128)
    module_id: Literal["m6"]
    contract_version: Literal["v1.0"]
    context_snapshot_id: str = Field(min_length=1)
    artifact_refs: list[ContractArtifactReference] = Field(default_factory=list, max_length=100)
    status: Literal[
        "requested",
        "ready",
        "running",
        "awaiting_approval",
        "succeeded",
        "rejected",
        "failed_retryable",
        "failed_terminal",
        "superseded",
    ]
    warnings: list[str] = Field(default_factory=list)
    errors: list[dict[str, Any]] = Field(default_factory=list)
    correlation_id: str = Field(min_length=1, max_length=128)
    idempotency_key: str = Field(min_length=1, max_length=128)
    requested_by: str | None = Field(default=None, min_length=1, max_length=128)
    requested_at: datetime | None = None
    input_hash: str | None = Field(default=None, pattern=r"^sha256:[a-f0-9]{64}$")
    approval_refs: list[ContractApprovalReference] = Field(min_length=1, max_length=100)
    module_input: M6ModuleInput


class M7OperationalPolicy(StrictModel):
    audit_retention_required: bool
    quality_checks: list[str] = Field(default_factory=list)
    freshness_checks: list[str] = Field(default_factory=list)


class M7ModuleInput(StrictModel):
    project_artifacts: list[ContractArtifactReference] = Field(default_factory=list)
    execution_ids: list[str] = Field(default_factory=list)
    operational_policy: M7OperationalPolicy

    @field_validator("execution_ids")
    @classmethod
    def unique_execution_ids(cls, v: list[str]) -> list[str]:
        if len(v) != len(set(v)):
            raise ValueError("execution_ids must contain unique items")
        for item in v:
            if not item or not item.strip():
                raise ValueError("execution_id items cannot be empty")
        return v


class M7GovernanceRequest(StrictModel):
    project_id: str = Field(min_length=1)
    execution_id: str = Field(min_length=1, max_length=128)
    module_id: Literal["m7"]
    contract_version: Literal["v1.0"]
    context_snapshot_id: str = Field(min_length=1)
    artifact_refs: list[ContractArtifactReference] = Field(default_factory=list, max_length=100)
    status: Literal[
        "requested",
        "ready",
        "running",
        "awaiting_approval",
        "succeeded",
        "rejected",
        "failed_retryable",
        "failed_terminal",
        "superseded",
    ]
    warnings: list[str] = Field(default_factory=list)
    errors: list[dict[str, Any]] = Field(default_factory=list)
    correlation_id: str = Field(min_length=1, max_length=128)
    idempotency_key: str = Field(min_length=1, max_length=128)
    requested_by: str | None = Field(default=None, min_length=1, max_length=128)
    requested_at: datetime | None = None
    input_hash: str | None = Field(default=None, pattern=r"^sha256:[a-f0-9]{64}$")
    approval_refs: list[ContractApprovalReference] = Field(default_factory=list, max_length=100)
    module_input: M7ModuleInput


class M7ProjectState(StrictModel):
    current_phase: str = Field(min_length=1)
    module_statuses: dict[str, str] = Field(default_factory=dict)
    blocked_reasons: list[str] = Field(default_factory=list)


class M7OperationalIndicator(StrictModel):
    name: str = Field(min_length=1)
    classification: Literal["measured", "estimated", "hypothesis", "documentary_evidence"]
    value_status: str = Field(min_length=1)
    source_artifact: ContractArtifactReference | None = None


class M7MaintenancePlan(StrictModel):
    procedures: list[str] = Field(default_factory=list)
    future_controls: list[str] = Field(default_factory=list)


class M7ModuleOutput(StrictModel):
    audit_artifact: ContractArtifactReference
    project_state: M7ProjectState
    operational_indicators: list[M7OperationalIndicator] = Field(default_factory=list)
    maintenance_plan: M7MaintenancePlan


class M7NextAction(StrictModel):
    action: str = Field(min_length=1)
    requires_approval: bool
    target_module: Literal["m1", "m2", "m3", "m4", "m5", "m6", "m7", "m8"] | None = None
    hypothesis: str | None = None


class M7GovernanceResult(StrictModel):
    project_id: str = Field(min_length=1)
    execution_id: str = Field(min_length=1, max_length=128)
    module_id: Literal["m7"] = "m7"
    contract_version: Literal["v1.0"] = "v1.0"
    context_snapshot_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1, max_length=128)
    status: Literal[
        "succeeded",
        "awaiting_approval",
        "rejected",
        "failed_retryable",
        "failed_terminal",
        "superseded",
    ]
    artifacts: list[ContractArtifactReference] = Field(default_factory=list)
    approval_refs: list[ContractApprovalReference] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[dict[str, Any]] = Field(default_factory=list)
    next_actions: list[M7NextAction] = Field(default_factory=list)
    completed_at: datetime | str | None = None
    output_hash: str | None = Field(default=None, pattern=r"^sha256:[a-f0-9]{64}$")
    module_output: M7ModuleOutput


class ContractCitation(StrictModel):
    citation_id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    locator: str = Field(min_length=1)
    evidence_type: Literal[
        "technical_documentation",
        "research",
        "standard",
        "project_artifact",
        "experience_record",
        "hypothesis",
    ]
    retrieved_at: datetime | None = None
    limitations: list[str] = Field(default_factory=list)


class ClaimPolicy(StrictModel):
    required_classification: Literal[True] = True
    require_source_reference: Literal[True] = True
    allow_hypotheses: bool | None = Field(default=None, strict=True)


M8ClaimPolicy = ClaimPolicy


class M8ModuleInput(StrictModel):
    context_artifacts: list[ContractArtifactReference]
    result_artifacts: list[ContractArtifactReference]
    claim_policy: ClaimPolicy


class M8DashboardInput(StrictModel):
    project_id: str = Field(min_length=1)
    execution_id: str = Field(min_length=1, max_length=128)
    module_id: Literal["m8"] = "m8"
    contract_version: str = Field(default="v1.0", pattern=r"^v[0-9]+(?:\.[0-9]+){0,2}$")
    context_snapshot_id: str = Field(min_length=1)
    artifact_refs: list[ContractArtifactReference] = Field(default_factory=list, max_length=100)
    status: Literal[
        "requested",
        "ready",
        "running",
        "awaiting_approval",
        "succeeded",
        "rejected",
        "failed_retryable",
        "failed_terminal",
        "superseded",
    ] = "requested"
    warnings: list[str] = Field(default_factory=list)
    errors: list[dict[str, Any]] = Field(default_factory=list)
    correlation_id: str = Field(min_length=1, max_length=128)
    idempotency_key: str = Field(min_length=1, max_length=128)
    requested_by: str | None = Field(default=None, min_length=1, max_length=128)
    requested_at: datetime | None = None
    input_hash: str | None = Field(default=None, pattern=r"^sha256:[a-f0-9]{64}$")
    approval_refs: list[ContractApprovalReference] = Field(default_factory=list, max_length=100)
    module_input: M8ModuleInput


M8DashboardRequest = M8DashboardInput


class DashboardClaim(StrictModel):
    claim: str = Field(min_length=1)
    classification: Literal["measured", "estimated", "hypothesis", "documentary_evidence"]
    source_artifacts: list[ContractArtifactReference]
    citations: list[ContractCitation] = Field(default_factory=list)


M8DashboardClaim = DashboardClaim


class DashboardSection(StrictModel):
    section_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    claims: list[DashboardClaim]


M8DashboardSection = DashboardSection


class DashboardRoadmapItem(StrictModel):
    item: str = Field(min_length=1)
    dependencies: list[str] = Field(default_factory=list)
    success_signal: str = Field(min_length=1)


M8RoadmapItem = DashboardRoadmapItem


class M8ModuleOutput(StrictModel):
    dashboard_artifact: ContractArtifactReference
    sections: list[DashboardSection] = Field(min_length=1)
    roadmap: list[DashboardRoadmapItem] = Field(default_factory=list)


class M8NextAction(StrictModel):
    action: str = Field(min_length=1)
    requires_approval: bool
    target_module: Literal["m1", "m2", "m3", "m4", "m5", "m6", "m7", "m8"] | None = None
    hypothesis: str | None = None


class M8DashboardOutput(StrictModel):
    project_id: str = Field(min_length=1)
    execution_id: str = Field(min_length=1, max_length=128)
    module_id: Literal["m8"] = "m8"
    contract_version: str = Field(default="v1.0", pattern=r"^v[0-9]+(?:\.[0-9]+){0,2}$")
    context_snapshot_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1, max_length=128)
    status: Literal[
        "succeeded",
        "awaiting_approval",
        "rejected",
        "failed_retryable",
        "failed_terminal",
        "superseded",
    ] = "succeeded"
    artifacts: list[ContractArtifactReference] = Field(default_factory=list)
    approval_refs: list[ContractApprovalReference] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[dict[str, Any]] = Field(default_factory=list)
    next_actions: list[M8NextAction] = Field(default_factory=list)
    completed_at: datetime | None = None
    output_hash: str | None = Field(default=None, pattern=r"^sha256:[a-f0-9]{64}$")
    module_output: M8ModuleOutput


M8DashboardResult = M8DashboardOutput
