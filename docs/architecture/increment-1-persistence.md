# Increment 1 Persistence Decisions

Status: Corrected for review

## Scope

This increment implements the persistence boundary and initial API only. It does not implement the frontend, agents M1-M8, RAG, or the orchestrator state machine.

## Persistence decisions

- SQLAlchemy is used as the ORM and repository boundary.
- PostgreSQL is the intended runtime database and is configured through `DATABASE_URL`.
- SQLite is used only by isolated local tests when PostgreSQL and its driver are unavailable in the execution environment.
- Alembic contains the versioned schema migrations under `backend/alembic/versions/0001_initial.py` through `0007_project_archiving.py`. The correction and archiving migrations are incremental and preserve earlier migration history.
- Artifact bytes are stored outside PostgreSQL through the `ArtifactStore` protocol and the local `LocalArtifactStore` implementation. PostgreSQL stores metadata, the server-generated storage identifier and the verified hash.
- Artifact identity is logical (`logical_id`) and each immutable version has a separate physical row identifier. New versions use the canonical `vN` form. The server determines the immediate predecessor, and the database enforces uniqueness by project, logical identity and version, plus a composite foreign key to the previous version of the same project and logical identity.
- Version one has no predecessor. Versions after `v1` require the immediately previous version; gaps, self-links and inconsistent predecessor numbers are rejected. The predecessor is not accepted as client input.
- Rows that predate the chain migration are marked `legacy_version` and remain unchanged. They are not assigned invented predecessors and cannot be extended through the new chain until a separate compatibility decision is approved.
- Artifact lineage and decision evidence use explicit association tables with foreign keys. Legacy identifier arrays remain as read-compatible projections, not as the integrity boundary.
- Context snapshots carry an explicit predecessor reference and are serialized under a project row lock before the next version is assigned.
- Context snapshots, audit events, decisions and artifacts are immutable. Artifacts have both ORM guards and database triggers; approvals may only change their resolution fields once.
- Project deletion is not exposed; the ORM rejects deletion and audit foreign keys use restrictive semantics in the incremental migration. Logical archiving uses `projects.archived_at` and `projects.archived_from_status`, preserves all historical relations, records `project.archived`/`project.restored` events and makes archived projects read-only until restoration.

## Canonical hashing

Context hashes are calculated over UTF-8 JSON using:

- UTF-8 encoding.
- `ensure_ascii=False`.
- `allow_nan=False`.
- Sorted object keys.
- Compact separators `,` and `:`.
- SHA-256 output prefixed with `sha256:`.

The same canonicalization helper is used for audit input hashes and approval scopes. Approval scopes are calculated on the server from the project, action, scope type, exact artifact reference, execution and decision references.

## Approval behavior

An approval is created as `pending` with a typed project, artifact or execution scope. Artifact-scoped approvals require an exact logical artifact identifier and version. The server calculates the scope hash and rejects a client-supplied hash that does not match. Resolution is a one-way operation to `approved` or `rejected`; immutable scope fields cannot be changed.

## Security boundary

The API does not implement enterprise authentication or complete multi-user isolation in this increment. Project identifiers and organization fields are persisted so those controls can be added behind the API boundary. Audit metadata and artifact metadata are recursively redacted for secret-like keys. This backend remains local-review-only until authorization and project isolation are implemented.

## Operational safeguards

- `MAX_ARTIFACT_BYTES`, `MAX_METADATA_BYTES` and `MAX_CORRELATION_ID_LENGTH` are configurable environment limits.
- The `X-Correlation-ID` header is validated, returned in the response and propagated to audit events.
- Local artifact writes use server-generated UUIDs, an atomic data write, an integrity sidecar and a root containment check.
- The content endpoint computes the hash from received bytes. Metadata-only registration requires a server-side storage identifier and verifies the stored bytes before persistence.

## Migration operation

The active database must be upgraded through `0004 → 0005 → 0006 → 0007` from its recorded revision before deploying the application code that reads archive columns. The `0007` migration is additive, has a consistency check and refuses downgrade while archived rows exist. The application does not physically delete projects or audit events.
