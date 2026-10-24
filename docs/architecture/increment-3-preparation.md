# Increment 3 Data Preparation

## Scope

Increment 3 implements the M3 Data Preparation boundary from CRISP-DM. It
consumes project-scoped M2 Bronze manifests, reads the preserved CSV or Excel
sources through the local ArtifactStore, applies an explicit deterministic
transformation plan and produces immutable Silver and Gold CSV artifacts.

The implementation remains behind the central `ProjectOrchestrator`. M3 does
not invoke M4, a model provider, a cloud connector or a paid service.

## Contract decision

The original M3 contract represented a transformation action as free text and
did not describe the output while a material transformation awaited human
approval. Contract version `v1.1` resolves that ambiguity. The executable
action vocabulary is limited to:

- `normalize_column_names`
- `drop_duplicate_rows`
- `fill_missing_values`
- `parse_date_columns`
- `drop_empty_rows`

Unknown actions, invalid parameters and missing referenced columns are rejected
explicitly. Business rules remain recorded as context; free-form business rules
are not executed as code.

## Approval behavior

When a rule has `approval_required: true`, M3 requires an approved
`approve_transformations` approval for every input Bronze artifact. The
approval is checked on the server against the project, exact artifact version
and stored scope hash. Without those approvals M3 persists an
`awaiting_approval` execution and returns a preview summary without claiming
that Silver or Gold exists. Once the same idempotency key is retried with the
approved references, the transformation may proceed.

## Outputs and lineage

Silver is a prepared CSV generated from the preserved source data. Gold is the
same deterministic prepared dataset as the consumption baseline because the
M3 contract does not yet define a target variable, feature-selection policy or
analytical schema. Both are immutable version-one artifacts. Bronze is a parent
of Silver and Silver is a parent of Gold through the existing project-scoped
artifact lineage constraints.

M3 uses the existing `executions`, `artifacts` and `artifact_lineage` tables;
no additional migration is required. A relational DatasetVersion entity is
still deferred until a later increment needs richer dataset metadata than the
artifact contract provides.

## Quality policy

M3 evaluates the deterministic checks `non_empty_dataset`, `columns_present`,
`no_duplicate_rows` and `no_missing_values`. Unknown checks are reported as
limitations rather than silently treated as passed. A failed check named in
`blocking_conditions` produces a terminal, traceable execution without
creating Silver or Gold artifacts.

The original source bytes are never overwritten. CSV parsing options captured
by M2 are carried in the Bronze manifest; older Bronze manifests without those
optional fields use documented format defaults and remain readable.
