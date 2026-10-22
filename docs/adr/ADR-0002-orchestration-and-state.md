# ADR 0002 Orchestration and State

Status: Accepted for MVP planning

## Context

The product document requires eight specialized modules, a persistent project context, iterative CRISP-DM flow, explicit approvals and traceability. Independent assistants or direct module-to-module calls would make prerequisites, retries and human decisions difficult to audit.

## Decision

Use one central orchestrator as the only component allowed to advance a project. Modules are invoked through versioned contracts and return structured results. The orchestrator persists every execution, transition, decision, approval and artifact relationship.

## State model

Each module run may be in one of these states:

- `not_started`
- `ready`
- `running`
- `awaiting_approval`
- `succeeded`
- `rejected`
- `failed_retryable`
- `failed_terminal`
- `superseded`

The project has a current phase derived from its module runs and an append-only history of transitions. A material correction creates a new execution and does not overwrite the prior execution.

## Transition rules

1. Only the orchestrator can create a runnable module execution.
2. A module requires all declared prerequisite artifacts and approvals.
3. Inputs reference exact artifact versions and content hashes.
4. Approval records are scoped to an action, project, execution and artifact version.
5. A rejected proposal must create a new decision or an explicitly requested iteration.
6. M5 can route to M3 or M4 only with a hypothesis, objective and success signal.
7. M6 may generate local artifacts but cannot create cloud resources during the MVP.
8. A retryable failure may be retried with the same idempotency key; completed artifacts are reused rather than duplicated.
9. A terminal failure stops progression until a user changes the input, policy or decision.
10. The configurable iteration limit prevents an unbounded test-and-error loop.

## Approvals

Required approval points include:

- Selection of the M1 alternative.
- Material data interpretation or record exclusion in M2.
- Material transformations in M3.
- Selection of a candidate for formal evaluation in M4.
- Acceptance of the M5 recommendation.
- Any action involving cost, external data transmission, credentials or cloud infrastructure.

An approval is not a credential. It records user intent; authorization and permissions must still be enforced by the execution environment.

## Retry and idempotency

Each execution has an idempotency key and correlation identifier. A worker claims a pending execution using a durable database lock. Reprocessing the same key must return the existing execution result or a clearly recorded retry attempt. Artifact creation uses content hashes, server-derived predecessor chains and unique version relationships to prevent silent duplication or version gaps.

## Consequences

Positive consequences:

- The complete workflow is inspectable.
- Agents remain specialized and replaceable.
- Iterations retain evidence instead of erasing prior work.
- Human approvals become enforceable workflow gates.

Trade-offs:

- The orchestrator and state model are foundational work before analytical features.
- Contracts and migrations need disciplined versioning.
- A future high-scale workflow engine may be required, but it can be introduced behind the orchestration boundary.
