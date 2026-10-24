# Data Model

Status: Expanded during Increments 1 and 2; PostgreSQL validation is performed on isolated databases.

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

The M2 boundary currently represents the Bronze dataset as an immutable versioned artifact containing a canonical ingestion manifest and profile. The original CSV or Excel bytes remain in the source artifact. A dedicated relational `DatasetVersion` entity is deferred until M3 needs Silver and Gold transformation lineage.

### Transformation

Stores input dataset versions, output dataset version, rule specification, engine version, impact counts, approval reference and quality results.

### Experiment and ModelCandidate

An experiment stores the problem type, dataset version, split policy, seed, parameter configuration and results artifact. A model candidate stores the pipeline artifact, framework metadata, status and links to evaluations.

### DeploymentPlan

Stores target type, package artifact, configuration artifact, permissions, rollback plan, cost status and required approval. The MVP allows local and Docker artifact targets; cloud plans are informational only.

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
