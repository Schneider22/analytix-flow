# ADR 0008 M5 Evidence Evaluation Boundary

## Status

Accepted for Increment 5.

## Context

M4 emits immutable candidate pipelines, an experiment specification and
measured preliminary results. Its current persisted experiment does not
include exact row indices or fold assignments, and project success criteria
are textual. Treating those inputs as a fresh formal evaluation would require
inventing thresholds or silently retraining a candidate.

## Decision

Implement M5 as a deterministic evidence-review module behind the central
orchestrator. It accepts candidate pipeline references and a Gold reference,
resolves them server-side, and requires them to come from the same successful
M4 execution and project. It reuses only measured M4 metrics, compares them
with the recorded baseline, verifies the declared validation strategy and
persists an immutable `evaluation.m5` report with artifact lineage.

The result is `awaiting_approval` with a `record_insufficient_evidence`
decision request. The module never retrains, selects, deploys or calls an
external model provider. A future contract revision may enable independent
replay once M4 persists exact partition evidence and the product defines
machine-evaluable success criteria.
M5 also verifies the persisted M4 result hash before reusing its measured
evidence.

M5 requires one approved, artifact-scoped `select_model_candidate` approval
per evaluated candidate. The server resolves each approval ID and verifies
the project, action, status, scope hash and physical artifact version before
the evidence review proceeds.

## Consequences

- No Alembic migration is needed; existing execution and artifact persistence
  provide the required traceability.
- Cross-project, cross-execution, missing-metric and inconsistent-evidence
  failures are visible validation errors.
- The MVP makes the evidence limitation explicit instead of claiming formal
  generalization or business impact.
- Human approval remains required before acceptance or iteration.
