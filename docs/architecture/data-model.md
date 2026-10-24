# Data Model

Status: Expanded during Increments 1 through 5; PostgreSQL validation is performed on isolated databases.

## Design goals

The data model must preserve project history, make artifacts addressable by immutable versions, bind approvals to exact actions and allow the orchestrator to reconstruct why a module was or was not executed.

## Identifier conventions

- `project_id`: stable project identifier.
- `execution_id`: one attempted execution of one module.
- `module_id`: one of `m1` through `m8`.
- `context_snapshot_id`: immutable snapshot of the project context.
- `artifact_id`/`logical_id`: logical artifact identity at the API/database boundary.
- `Artifact.id`: immutable physical row identifier for one artifact version.
- `artifact_version`: immutable human-readable version label.
- `decision_id`: immutable decision record.
- `approval_id`: immutable approval or rejection record.
- `correlation_id`: request and event trace identifier.
- `content_hash`: SHA-256 hash of artifact bytes or canonical structured content.

IDs are opaque externally. References must include the logical identifier and the exact version where versioning applies.

## Core entities

### Project

Stores organization scope, name, owner, current phase, project status, success criteria and timestamps. It does not contain mutable copies of every module result.

### ProjectContextSnapshot

Stores a versioned snapshot of company, business need, objective, business rules, restrictions, assumptions and criteria of success. Each snapshot points to its predecessor and records its creator.

### ModuleRun

The `executions` table is the Increment 2 persistence representation of a module run. It stores module, execution, contract version, input snapshot, status, idempotency key, timestamps, error summary, output hash and the structured result envelope. The unique project/module/idempotency key constraint prevents duplicate M2 work.

### Artifact

Stores artifact type, logical identity, canonical numeric version (`v1`, `v2`, ...), content hash, media type, local URI, producer module, source execution, parent artifacts, the physical version identifier and creation metadata. Artifact content is immutable. Version one has no predecessor. Every later version stores a server-selected predecessor physical identifier and the predecessor version number.

### Decision

Stores the question, available options, selected option, rationale, evidence references, decision status and actor. Decisions are not overwritten when a later iteration changes the choice.

### Approval

Stores action, subject project, execution, artifact and version, scope hash, approver, role, status, rationale and timestamp. Approval is valid only for the exact scope recorded.

### DatasetVersion

M2 represents the Bronze dataset as an immutable versioned artifact containing
a canonical ingestion manifest and profile. M3 represents Silver and Gold as
immutable versioned artifacts with relational `artifact_lineage` edges. The
original CSV or Excel bytes remain in the source artifact. A dedicated
relational `DatasetVersion` entity remains deferred because the M3 contract
does not yet define target-variable, feature-selection or richer dataset
metadata semantics.

### Transformation

Stores input dataset versions, output dataset version, rule specification, engine version, impact counts, approval reference and quality results.

### Experiment and ModelCandidate

An experiment stores the problem type, dataset version, split policy, seed, parameter configuration and results artifact. A model candidate stores the pipeline artifact, framework metadata, status and links to evaluations.

### EvaluationReport

M5 stores an immutable `evaluation.m5` artifact in the existing `artifacts`
table. Its JSON content records the M4 execution and experiment references,
Gold reference, declared baseline, requested metrics, measured comparisons,
criteria assessment, reproducibility and leakage-review status, limitations and
the human decision request. The report is linked through `artifact_lineage` to
the Gold artifact, the M4 experiment and the evaluated candidate pipeline
artifacts. M5 reuses `executions`, `artifacts` and `artifact_lineage`; no new
relational table or migration is required.

### DeploymentPlan

M6 represents the deployment plan through an immutable `deployment.package`
artifact, an immutable `deployment.config` artifact and the existing
artifact-scoped `approve_deployment_action` approval. The package and config
are linked to the exact selected `model.pipeline` version through
`artifact_lineage`; no new relational table is required. The plan records the
target type, permissions, rollback statement, cost classification and the
fact that cloud execution is disabled. M6 only prepares descriptors and
hash-verified local consumption; it may read model bytes for SHA-256
verification but does not deserialize or execute model binaries, start
processes, build images or create cloud resources.

### KnowledgeSource, KnowledgeChunk and Citation

Knowledge sources retain provenance and limitations. Chunks reference their source. Citations reference a source, locator, retrieval context and consuming artifact or decision.

### AuditEvent

Stores actor type, actor identifier, action, module, input and output hashes, policy decision, correlation identifier and timestamp. Audit events are append-only.

### OperationalEvent

Stores execution errors, latency, availability, data quality, freshness, resource usage and incident references. It is separate from the immutable decision history.

## Relationships

```text
Project 1---N ContextSnapshot
Project 1---N ModuleRun
Project 1---N Decision
Project 1---N Approval
Project 1---N Artifact
ModuleRun 1---N Artifact
Artifact N---N Artifact       (parent/derived lineage)
Artifact 1---N Artifact       (mandatory predecessor chain for v2+)
Artifact 1---N DatasetVersion
DatasetVersion 1---N Transformation
Experiment N---1 DatasetVersion
ModelCandidate N---1 Experiment
ModelCandidate 1---N EvaluationReport
Decision 1---N Approval
KnowledgeSource 1---N KnowledgeChunk
KnowledgeSource 1---N Citation
Project 1---N AuditEvent
Project 1---N OperationalEvent
```

`project_context_snapshots.predecessor_id` is protected by a composite
same-project foreign key. Migration `0005_persistence_compatibility_repairs`
repairs databases that had already recorded `0004` before this constraint and
the complete PostgreSQL immutability trigger set were present. `artifact_lineage` and `decision_artifact_evidence` store a denormalized
`project_id` relationship scope. Incremental migration `0004` backfills that
scope from the existing child artifact or decision and adds composite foreign
keys so direct PostgreSQL writes cannot mix projects. Approval artifact and
decision references use the approval's existing `project_id` through the same
composite-key pattern. The migration aborts before changing schema objects if
existing cross-project rows are detected. Evidence rows retain their existing
decision-scoped `ON DELETE CASCADE`; audit events remain independent append-only
records. The compatibility repair also aborts on cross-project or orphaned
context predecessors before replacing the historical single-column FK.

## Versioning rules

1. Existing artifact versions are never mutated.
2. The first version of a logical artifact is `v1` and has no predecessor.
3. The server creates `vN` only when `vN-1` exists for the same project and logical identity; the database enforces uniqueness for `(project_id, logical_id, version_number)`, while the composite foreign key and checks enforce that relationship.
4. Clients cannot select or replace the predecessor. A version gap, cross-project reference, cross-identity reference, self-reference or inconsistent predecessor is rejected.
5. Historical rows created before the chain migration are marked as legacy because their predecessor relationship cannot be inferred without inventing data. A legacy logical identity cannot be extended until an explicit compatibility migration is approved.
6. A new transformation or interpretation creates a new dataset version.
7. Context snapshots are append-only and identify their predecessor.
8. Contract changes require a new `contract_version`.
9. A decision change creates a new decision or iteration record.
10. All derived artifacts retain parent references and content hashes.

## Audit requirements

Every module execution must be reconstructible from its input artifact references, context snapshot, contract version, policy, output artifacts, approvals and audit events. The model must retain failed executions and rejected approvals rather than deleting them.

Increment 2 adds the first executable module boundary for M2. The central orchestrator creates one execution record, validates the project-scoped context and source artifacts, invokes only the deterministic ingestion module, and persists the result and audit events. It does not advance M3 automatically.

Increment 3 adds the bounded M3 preparation boundary. The orchestrator validates
Bronze inputs and approvals, M3 applies only the versioned deterministic action
vocabulary, and the resulting Silver and Gold artifacts retain project-scoped
lineage. An awaiting-approval result contains no dataset claims.

Increment 4 adds the bounded M4 modeling boundary without a schema migration.
M4 stores an experiment specification, one pipeline artifact and one parameter
artifact per candidate through the existing immutable `artifacts` table and
`artifact_lineage` relationships. Experiment artifacts retain the Gold dataset
and problem-definition references. Candidate artifacts retain the experiment
reference. Supervised runs include a measured baseline comparison; descriptive
runs produce a measured profile and no predictive effectiveness claim. The
`select_model_candidate` approval is requested for the candidate artifact and
is consumed by a later evaluation increment; M4 does not select or deploy a
candidate.

Increment 5 adds the bounded M5 evaluation boundary without a schema
migration. M5 consumes only successful M4 execution evidence, validates that
all candidates and the Gold artifact belong to the same project and M4 run,
persists an immutable evaluation report and returns `awaiting_approval`.
Metrics remain classified as measured preliminary evidence from M4. The
module does not retrain, select, deploy or call an external provider.

Increment 6 adds the bounded local deployment and consumption boundary
without a schema migration. M6 requires a server-verified `accept_model`
approval for one exact M4 `model.pipeline` version, writes immutable package
and configuration artifacts, and creates a pending artifact-scoped
`approve_deployment_action` approval. The result remains
`awaiting_approval`; consumption uses the existing local ArtifactStore and
verifies the stored SHA-256 before returning bytes. Docker and cloud targets
are represented as local plan descriptors only.
