# ADR 0005 M2 ingestion boundary

## Status

Accepted for Increment 2.

## Decision

Implement M2 as a deterministic, local module behind the central project
orchestrator. Source bytes are registered first through the existing
server-hashed ArtifactStore endpoint. M2 receives exact artifact references,
reads verified bytes, profiles CSV and Excel content with pandas and writes a
canonical Bronze manifest as a new immutable artifact.

Add a project-scoped `executions` table in migration `0006_m2_ingestion`.
Execution identity is the client-provided execution ID, while idempotency is
enforced by `(project_id, module_id, idempotency_key)`. The execution also
stores the input hash, context snapshot, contract version, result envelope and
output hash so a replay does not duplicate artifacts.

## Consequences

- The original bytes and their hashes remain unchanged.
- Duplicate M2 requests with the same input return the persisted result.
- CSV, XLSX and XLS are supported locally; Parquet and generic cloud sources
  remain outside this increment.
- M2 reports quality and interpretation issues but does not silently clean data.
- A Bronze manifest is produced for a parse failure so the failure and recovery
  path remain traceable without inventing a successful profile.
- No module can invoke M3; later orchestration transitions require a separate
  increment and approval policy.
