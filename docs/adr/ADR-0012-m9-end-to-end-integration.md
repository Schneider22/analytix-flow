# ADR-0012: M9 End-to-End Integration and Lifecycle Verification

## Status

Accepted for Increment 9 MVP implementation.

## Context

The AnalytixFlow product rector document (`docs/AnalytixFlow.docx`, paragraphs 159–169 and 179) defines the foundational acceptance criteria for the entire analytical MVP:
1. The platform must complete a real, reproducible end-to-end analytical cycle guided by CRISP-DM across all eight specialized modules (M1–M8).
2. Every module must consume verifiable, cryptographically hashed inputs and produce immutable, versioned artifacts with traceable lineage.
3. Every material advancement or irreversible action must enforce explicit human approvals.
4. The executive dashboard (M8) must synthesize the full project evidence while strictly distinguishing measured facts, estimates, hypotheses, and documentary references.
5. Every experiment and test must be repeatable with identical data and configurations to prove algorithmic and architectural determinism.

Increments 1 through 8 delivered the individual capabilities, database schemas, storage subsystem, domain logic engines, and REST endpoints for:
- M1: Business Context and Architecture Decisions
- M2: Data Ingestion and Bronze Profiling
- M3: Data Preparation, Quality Gates, and Silver/Gold Datasets
- M4: Analytical Modeling and Candidate Generation
- M5: Empirical Evidence Evaluation and Holdout Verification
- M6: Local Deployment Packaging and Plan Specification
- M7: Continuous Governance, Audit Logging, and Operational Indicators
- M8: Executive Dashboard Synthesis and Evidence Consolidation

However, the existing test suites validate each module in isolation or with pre-canned, mock inputs. There is currently no single automated suite that executes the complete sequence M1 -> M2 -> M3 -> (Approval) -> M4 -> (Approval) -> M5 -> (Approval) -> M6 -> M7 -> M8 on a single project, verifying end-to-end data flow, multi-hop relational lineage, human gate transitions, multi-project isolation, and reproducible execution.

## Decision

We establish the end-to-end integration strategy for Increment 9 (M9) based on an automated, deterministic test scenario that exercises the real production API and Orchestrator boundaries without mocking intermediate modules.

### 1. Synthetic Customer Churn Problem Definition

To validate tabular, supervised machine learning capabilities in a self-contained, reproducible environment:
- **Domain**: Telecommunications Customer Churn Prediction (`classification`).
- **Organization**: `TelcoGlobal Synthetic Services`.
- **Business Need**: Identify subscribers at risk of cancellation to prioritize retention interventions.
- **Analytical Problem**: Supervised binary classification predicting `churn_label` (0 = active, 1 = churned) from customer tenure, financial charges, and contract features.
- **Data Character**: 100% synthetic data generated deterministically using Python standard libraries and numpy with a fixed seed (`seed=42`).
- **Evidence Integrity**: All generated records are explicitly declared and tagged as synthetic test data. They are never portrayed as real commercial evidence of model effectiveness.

### 2. Deterministic Dataset Specification

The source dataset (`synthetic_telco_churn.csv`) consists of exactly 100 rows and 6 columns:
1. `customer_id` (string): Unique identifier formatted as `CUST-0001` through `CUST-0100`.
2. `tenure_months` (integer): Subscription tenure in months (range: 1 to 72).
3. `monthly_charges` (float): Monthly service fee rounded to 2 decimal places (range: $18.50 to $118.75).
4. `total_charges` (float): Cumulative charges calculated as `tenure_months * monthly_charges` with controlled noise, formatted to 2 decimals.
5. `contract_type` (string): Categorical feature with values `month-to-month`, `one-year`, `two-year`.
6. `churn_label` (integer): Ground-truth binary target (0 or 1), generated via a deterministic sigmoid probability function conditioned on `tenure_months` and `monthly_charges`.

*Note: The actual CSV file generation logic is encapsulated inside the test fixtures for Phase 2; no static dummy CSV file is committed to the repository in Phase 1.*

### 3. End-to-End Execution Sequence and Module Contracts

The integration scenario executes sequentially across the verified REST endpoints of [`backend/app/api.py`](file:///c:/Users/Jose/Documents/Proyectos_2026/analytix-flow/backend/app/api.py) and methods of [`backend/app/orchestrator.py`](file:///c:/Users/Jose/Documents/Proyectos_2026/analytix-flow/backend/app/orchestrator.py):

#### Step 1: M1 — Project Initialization, Business Context, and Decision
- **Endpoints**:
  - `POST /api/v1/projects`: Creates project with `company_name="TelcoGlobal Synthetic Services"`, `business_need="Reduce churn"`, and `status="active"`.
  - `POST /api/v1/projects/{project_id}/context`: Creates immutable `ProjectContextSnapshot` (v1) with problem description, success criteria, and constraints.
  - `POST /api/v1/projects/{project_id}/decisions`: Records `Decision` of type `select_alternative` choosing the supervised classification strategy.
  - `POST /api/v1/projects/{project_id}/approvals`: Records human approval for the M1 alternative decision.
- **Outputs**: `project_id`, `context_snapshot_id` (v1).

#### Step 2: M2 — Data Registration and Bronze Ingestion
- **Prerequisites**: `project_id`, `context_snapshot_id`.
- **Endpoints**:
  - `POST /api/v1/projects/{project_id}/artifacts/content`: Uploads raw CSV bytes to `ArtifactStore`, registering artifact with `layer="source"`, `media_type="text/csv"`, returning `source_artifact`.
  - `POST /api/v1/projects/{project_id}/executions/m2`: Executes `M2IngestionRequest` with `source_artifacts=[source_artifact]` and `format="csv"`.
- **Outputs**:
  - `dataset.bronze` (`layer="bronze"`, Bronze manifest JSON).
  - `report.profile` (`layer="report"`, tabular profiling summary).
  - Relational lineage: `dataset.bronze -> source_artifact`.

#### Step 3: M3 — Preparation, Quality Policy, and Silver/Gold Datasets
- **Prerequisites**: `project_id`, `context_snapshot_id`, `dataset.bronze`.
- **Endpoints**:
  - `POST /api/v1/projects/{project_id}/executions/m3`: Invokes `M3PreparationRequest` with transformation rules:
    - `normalize_column_names` (`approval_required=False`).
    - `fill_missing_values` (`approval_required=True` on `total_charges`).
    - `drop_duplicate_rows` (`approval_required=False`).
  - **Human Gate 1 (M3)**: Initial execution returns `status="awaiting_approval"`.
  - `POST /api/v1/projects/{project_id}/approvals/{approval_id}/resolve`: Resolves approval with `action="approve_transformations"`, `status="approved"`.
  - Re-run `POST /api/v1/projects/{project_id}/executions/m3`: Advances to `status="succeeded"`.
- **Outputs**:
  - `dataset.silver` (`layer="silver"`).
  - `dataset.gold` (`layer="gold"`).
  - `report.quality` (`layer="report"`).
  - Relational lineage: `Silver -> Bronze`, `Gold -> Silver`.

#### Step 4: M4 — Modeling Experiments and Candidate Generation
- **Prerequisites**: `project_id`, `context_snapshot_id`, `dataset.gold`.
- **Endpoints**:
  - `POST /api/v1/projects/{project_id}/executions/m4`: Invokes `M4ModelingRequest` with `target_column="churn_label"`, `allowed_techniques=["logistic_regression", "decision_tree_classifier"]`, `split_policy.strategy="holdout"`, `split_policy.test_fraction=0.25`, and `reproducibility.random_seed=42`.
- **Outputs**:
  - `model.pipeline` / `model.registry` (`layer="model"`).
  - `experiment.m4` (`layer="report"`).
  - Emitted next action: `action="select_candidate"`, `requires_approval=True`.
  - Relational lineage: Models descend from `dataset.gold`.

#### Step 5: Human Gate 2 (Candidate Selection for M5)
- **Endpoints**:
  - `POST /api/v1/projects/{project_id}/approvals`: Creates approval record for candidate model with `action="select_candidate"`.
  - `POST /api/v1/projects/{project_id}/approvals/{approval_id}/resolve`: Resolves approval with `status="approved"`.

#### Step 6: M5 — Empirical Evaluation and Validation Gating
- **Prerequisites**: `project_id`, `context_snapshot_id`, `dataset.gold`, candidate model reference, approved candidate approval record.
- **Endpoints**:
  - `POST /api/v1/projects/{project_id}/executions/m5`: Invokes `M5EvaluationRequest` validating candidate performance against holdout test partition without fabricated metrics.
- **Outputs**:
  - `report.evaluation` (`layer="report"`).
  - Emitted next action: `action="approve_deployment"`, `requires_approval=True`.
  - Relational lineage: `report.evaluation` descends from candidate models and `dataset.gold`.

#### Step 7: Human Gate 3 (Model Approval for Deployment)
- **Endpoints**:
  - `POST /api/v1/projects/{project_id}/approvals`: Creates approval record for model deployment with `action="deploy_model"`.
  - `POST /api/v1/projects/{project_id}/approvals/{approval_id}/resolve`: Resolves approval with `status="approved"`.

#### Step 8: M6 — Local Deployment Package and Plan
- **Prerequisites**: `project_id`, `context_snapshot_id`, selected model reference, `report.evaluation`, approved deployment approval record.
- **Endpoints**:
  - `POST /api/v1/projects/{project_id}/executions/m6`: Invokes `M6DeploymentRequest` targeting `local_process` with strict local execution (`cloud_execution_allowed=False`, `network_access="denied"`, `secret_access="none"`).
- **Outputs**:
  - `deployment.package` (`layer="deployment"`).
  - `deployment.plan` (`layer="deployment"`).
  - Relational lineage: Package descends from selected model and evaluation report.

#### Step 9: M7 — Continuous Governance, Audit, and Operational State
- **Prerequisites**: `project_id`, `context_snapshot_id`, references to all prior artifacts and execution IDs (M1–M6).
- **Endpoints**:
  - `POST /api/v1/projects/{project_id}/executions/m7`: Invokes `M7GovernanceRequest` verifying project state, maintenance procedures, and computing operational indicators (`mvp_measured` vs `future_unmeasured`).
- **Outputs**:
  - `governance.audit` (`layer="audit"`).
  - Project state: all modules marked `succeeded`, `blocked_reasons=[]`.
  - Relational lineage: Audit artifact descends from all verified project artifacts.

#### Step 10: M8 — Executive Dashboard and Evidence Consolidation
- **Prerequisites**: `project_id`, `context_snapshot_id`, `context_artifacts` (M1 context, M2 source), `result_artifacts` (M2 bronze, M3 silver/gold, M4 model, M5 evaluation, M6 package, M7 audit), `claim_policy` (`required_classification=True`, `require_source_reference=True`, `allow_hypotheses=False`).
- **Endpoints**:
  - `POST /api/v1/projects/{project_id}/dashboard`: Invokes executive synthesis engine.
  - `GET /api/v1/projects/{project_id}/dashboard`: Retrieves persisted executive summary.
- **Outputs**:
  - `dashboard.report` (`layer="report"`).
  - Synthesis of 6 executive sections: `business_diagnosis`, `data_quality`, `analytical_strategy`, `evaluation_results`, `impact_and_costs`, `roadmap`.
  - Machine-actionable roadmap milestones.
  - Multi-hop lineage: `dashboard.report` records direct relational links in `artifact_lineage` to all referenced artifacts.

### 4. Artifact Reference Chaining Strategy

To guarantee that artifact references pass strict validation across module boundaries:
1. Every module response envelope exposes its newly created artifacts in the top-level list `result["artifacts"]` and within `result["module_output"]`.
2. Downstream requests extract the exact `ContractArtifactReference` dictionary:
   - `artifact_id`: Logical identifier (e.g. `m8-dashboard-report-...`).
   - `artifact_type`: Precise type string (`dataset.bronze`, `dataset.silver`, `dataset.gold`, `model.pipeline`, `report.evaluation`, `deployment.package`, `governance.audit`, `dashboard.report`).
   - `artifact_version`: Semantic version string (`v1`).
   - `version_number`: Integer (`1`).
   - `version_id`: Database primary key (UUID string).
   - `content_hash`: Cryptographic hash (`sha256:...`).
   - `uri`: Storage URI (`local-artifact://<storage_id>`).
   - `storage_id`: Storage UUID matching physical bytes in `LocalArtifactStore`.
   - `layer`: Valid layer string matching contract enums.
3. If an input contract schema permits omitting `uri` or `version_id`, the central Orchestrator resolves and enriches the reference from the verified database record before passing it to domain logic.

### 5. Multi-Project Isolation, Idempotency, and Determinism

1. **Multi-Project Isolation**:
   - The test scenario creates a secondary project (`proj-alien-002`).
   - The test asserts that `proj-alien-002` cannot read, reference, evaluate, or include any artifact or execution belonging to the primary project.
   - Any cross-project reference must fail with `404 Not Found` or `422/400 Validation Error`.
2. **Idempotency Replay**:
   - For every module (M2 through M8), the test immediately replays the execution request with the identical `execution_id`, `idempotency_key`, and payload.
   - The test asserts that the cached result is returned with HTTP 200/201, without triggering re-computation or creating duplicate physical artifacts.
3. **Deterministic Reproducibility**:
   - A separate test run re-executes the complete sequence on a clean database using the exact same synthetic dataset and random seed (`seed=42`).
   - The test asserts that the resulting model weights, performance metrics, and artifact content hashes match the initial run with zero divergence.

### 6. Test Suite Separation (SQLite vs. PostgreSQL)

1. **Primary Integration Suite (`backend/tests/test_m9_end_to_end.py`)**:
   - Runs against in-memory SQLite and local temporary `LocalArtifactStore`.
   - Uses FastAPI `TestClient(app)` to exercise the complete HTTP/REST lifecycle.
   - Fast, self-contained, and runnable in all local environments without external database daemons.
2. **PostgreSQL Integration Suite (`backend/tests/test_m9_end_to_end_postgres.py`)**:
   - Guards execution with `require_migrated_postgres` from `backend/tests/postgres_support.py`.
   - When `ANALYTIXFLOW_TEST_DATABASE_URL` is configured (CI/Docker), runs the full end-to-end integration against real PostgreSQL tables, enforcing database-level foreign keys, triggers, and row locks (`with_for_update=True`).
   - When PostgreSQL is unavailable (local host), skips cleanly (`SKIPPED`) without generating false failures or simulated results.

### 7. Verifiable Acceptance Criteria

The integration increment M9 will be considered complete and ready for closure when:
1. All steps in the M1–M8 sequence execute successfully via the REST API, returning HTTP 200 or 201.
2. Relational lineage links form a complete Directed Acyclic Graph (DAG) connecting `dashboard.report` back through M7, M6, M5, M4, M3, M2 to the source CSV.
3. Every human gate (`approve_transformations`, `select_candidate`, `deploy_model`) blocks execution until resolved and unblocks execution upon resolution.
4. M8 dashboard report strictly adheres to `claim_policy`: zero invented metrics, all claims classified into one of the four epistemic tiers, and all citations backed by verified source artifacts.
5. Deterministic replay yields identical SHA-256 hashes for all generated datasets and models.
6. Multi-project cross-referencing is rejected with 100% reliability.
7. Full regression suite (M1–M8) passes with zero failures and zero regressions.

### 8. Known Risks and Architectural Limitations

1. **M1 Implementation Boundary**:
   - M1 does not have an autonomous agent worker or a dedicated `orchestrator.run_m1` method.
   - M1 is realized through foundational entity creation: `POST /projects`, `POST /context`, `POST /decisions`, and `POST /approvals`.
   - M7 reflects M1 as `succeeded` whenever `project.status != "draft"`.
   - The E2E integration test respects this architecture and does not attempt to invoke a nonexistent `/executions/m1`.
2. **Sequential Human Gate Dependencies**:
   - M5 and M6 enforce strict database-level checks requiring prior approval records. The test driver must explicitly resolve approvals between execution phases.

### 9. Phase Plan for Increment 9

- **Fase 1 (Current)**: Architectural Decision Record (`docs/adr/ADR-0012-m9-end-to-end-integration.md`).
- **Fase 2**: Implementation of the primary end-to-end integration suite (`backend/tests/test_m9_end_to_end.py`) exercising M1–M8 under SQLite.
- **Fase 3**: Implementation of determinism replay, multi-project isolation, and PostgreSQL integration suite (`backend/tests/test_m9_end_to_end_postgres.py`).
- **Fase 4**: Full regression audit (130+ tests), diff verification, and preparation for commit and publication.

## Consequences

- A single, fully automated integration suite will validate the complete CRISP-DM analytical lifecycle of AnalytixFlow.
- Future frontend applications will have an exact, verified contract reference for how to drive an end-to-end project.
- Production code remains completely untouched in Phase 1, maintaining zero risk of regressions.
- All testing conforms to the repository's cryptographic and audit standards.
