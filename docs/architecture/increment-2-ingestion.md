# Increment 2 Data Ingestion

## Scope

Increment 2 implements only the M2 Data Understanding and Bronze boundary. It
accepts already registered source artifacts, verifies their server-side hashes,
profiles CSV and Excel content with pandas, preserves the original bytes and
creates an immutable Bronze manifest artifact.

The central `ProjectOrchestrator` is the only entry point for M2 execution.
The ingestion module does not call another module, a model provider or the
network. M3 preparation is not started automatically.

## Execution contract

`POST /api/v1/projects/{project_id}/executions/m2` requires the M2 input
contract, an exact project context snapshot, source artifact references and an
idempotency key. The server rejects references from another project, mismatched
content hashes, missing ingestion options and a reused key with different
input. A replay with the same key and input returns the persisted result.

The migration `0006_m2_ingestion` adds the project-scoped `executions` table.
Its composite context foreign key prevents an execution from using a snapshot
belonging to another project, and its unique project/module/idempotency key
constraint prevents duplicate execution records.

## Profiling behavior

CSV uses the declared encoding, delimiter and header row. Excel uses the
declared `xlsx` or `xls` format and profiles either the selected sheet or all
sheets. The report includes structures, row and column counts, data types,
missing values, duplicate-row warnings, temporal coverage and potential
identifiers. No source rows are removed or rewritten.

Parse failures are returned as terminal contract errors with a recovery option;
the original source artifact remains preserved. Material interpretation issues
are represented as issues requiring human review. The Bronze artifact is a
canonical JSON manifest and profile, not a replacement for the original bytes.

## Explicit limits

- Parquet and generic Data Lake connectors remain deferred.
- No transformations, Silver/Gold datasets, models, cloud actions or paid providers are executed.
- M2 does not decide business alternatives or approve transformations.
- The relational `DatasetVersion` entity is deferred until M3 requires transformation lineage.
