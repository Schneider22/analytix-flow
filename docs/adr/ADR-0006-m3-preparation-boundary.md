# ADR 0006 M3 preparation boundary

## Status

Accepted for Increment 3.

## Context

The M3 contract defines Silver and Gold outputs, transformation rules and
quality policies, but its original `action` field did not define executable
semantics. It also required dataset references even when the workflow must stop
for human review of a material transformation.

## Decision

Implement M3 as a deterministic local module behind the central orchestrator.
Contract version `v1.1` defines five supported actions: column-name
normalization, duplicate-row removal, missing-value filling, date parsing and
empty-row removal. Parameters are explicit and unsupported actions fail rather
than being guessed.

Material rules require one approved `approve_transformations` artifact-scoped
approval per input Bronze version. The execution can remain in
`awaiting_approval` and be resumed with the same idempotency key after the
approval is resolved. The approval references are excluded from the execution
input hash so the approval transition does not create duplicate work.

M3 produces immutable Silver and Gold artifacts and records parent lineage
using the existing artifact tables. Gold is a deterministic prepared baseline,
not a model-specific feature set; target-variable and feature-selection
semantics remain outside this increment.

## Consequences

- M3 is reproducible without a model provider, network access or cloud actions.
- A missing approval cannot be mistaken for an applied transformation.
- The existing Increment 2 schema is sufficient; no historical migration is
  changed and no new database migration is required.
- The action vocabulary is intentionally narrow. Extending it requires a new
  contract version, tests and an explicit decision about its parameters.
- The same source data may be read with format defaults when an older M2
  manifest predates the optional parsing metadata; the limitation is preserved
  in the artifact provenance rather than hidden.
