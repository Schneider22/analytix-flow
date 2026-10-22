# Data Model

Status: Proposed for Increment 0

## Design goals

The data model must preserve project history, make artifacts addressable by immutable versions, bind approvals to exact actions and allow the orchestrator to reconstruct why a module was or was not executed.

## Identifier conventions

- `project_id`: stable project identifier.
- `execution_id`: one attempted execution of one module.
- `module_id`: one of `m1` through `m8`.
- `context_snapshot_id`: immutable snapshot of the project context.
- `artifact_id`: logical artifact identity.
- `artifact_version`: immutable version of an artifact.
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

Stores module, execution, attempt, contract version, input snapshot, status, idempotency key, timestamps, error summary and output artifact references.

### Artifact

Stores artifact type, logical identity, version, content hash, media type, local URI, producer module, source execution, parent artifacts, classification and creation metadata. Artifact content is immutable.

### Decision

Stores the question, available options, selected option, rationale, evidence references, decision status and actor. Decisions are not overwritten when a later iteration changes the choice.

### Approval

Stores action, subject project, execution, artifact and version, scope hash, approver, role, status, rationale and timestamp. Approval is valid only for the exact scope recorded.

### DatasetVersion

Stores source artifact, data layer, schema artifact, profile artifact, row and column summaries, quality status, lineage references and transformation metadata.

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

## Versioning rules

1. Existing artifact versions are never mutated.
2. A new transformation or interpretation creates a new dataset version.
3. Context snapshots are append-only and identify their predecessor.
4. Contract changes require a new `contract_version`.
5. A decision change creates a new decision or iteration record.
6. All derived artifacts retain parent references and content hashes.

## Audit requirements

Every module execution must be reconstructible from its input artifact references, context snapshot, contract version, policy, output artifacts, approvals and audit events. The model must retain failed executions and rejected approvals rather than deleting them.
