# ADR 0004 Persistence Integrity Corrections

Status: Accepted for Increment 1 correction

## Context

The first Increment 1 review identified integrity gaps at the persistence boundary: artifact bytes had no storage abstraction, logical artifact identity was conflated with a physical row identifier, lineage and decision evidence were represented only as identifier arrays, context versions lacked an explicit predecessor, and approval scope could be supplied without a server-verifiable binding. These gaps would make later CRISP-DM executions, approvals and audit reconstruction ambiguous.

## Decision

Apply the following corrections without implementing the orchestrator, modules M1-M8, frontend, RAG or cloud deployment:

1. **Separate artifact bytes from metadata.** `ArtifactStore` is a provider-neutral port. The MVP implementation is `LocalArtifactStore`, which assigns storage UUIDs, writes bytes and a SHA-256 sidecar atomically, enforces a byte limit, rejects path traversal and verifies content before metadata is committed. PostgreSQL stores metadata, the storage identifier and the verified hash; it does not store the bytes.
2. **Separate logical and physical artifact identity.** `artifact_id`/`logical_id` is the project-scoped logical identity and `Artifact.id` is the immutable database row identifier for one version. New versions use `vN`. The database enforces uniqueness for `(project_id, logical_id, artifact_version)` and `(project_id, logical_id, version_number)`; every persisted strict version has a server-verified content hash.
3. **Enforce a server-derived predecessor chain.** The first version is `v1` with no predecessor. For `vN`, the service locks the project row, finds `vN-1` for the same logical identity and stores its physical identifier. A composite foreign key over physical id, project, logical identity and numeric version, plus check constraints, prevents gaps, cross-project links, cross-identity links, self-links and cycles. The client cannot provide the predecessor.
4. **Use explicit relationship tables.** Artifact lineage and decision evidence use foreign-key association tables. The automatically selected predecessor is also represented in artifact lineage. Existing JSON identifier arrays remain compatibility projections only and are not the integrity boundary.
5. **Preserve ambiguous historical rows.** Rows created before the chain migration are marked `legacy_version` and retain their original values. No predecessor is invented. A legacy logical identity cannot be extended by the new service until a separate compatibility migration is approved.
6. **Version context under a project lock.** A context snapshot records `predecessor_id`. The service locks the project row, reads the latest snapshot, assigns the next version and commits the new snapshot and audit event in one transaction.
7. **Make approval scope typed and canonical.** Approval scope is `project`, `artifact` or `execution`. The service validates action-to-scope rules, resolves exact artifact logical identity plus version, derives the canonical scope from server-side values and calculates `scope_hash`. A supplied hash is checked but never trusted. Scope fields are immutable and resolution is one-shot; only resolution fields may change.
8. **Preserve history.** Snapshots, artifacts, decisions and audit events are immutable. PostgreSQL triggers and ORM guards prevent direct or application-level mutation; approval scope is immutable while a pending approval may be resolved once. Project deletion is rejected by the ORM and the incremental migration changes project foreign keys to restrictive behavior for PostgreSQL. Archival/deactivation and retention policies remain separate decisions and no physical deletion endpoint is provided.
9. **Bound and trace requests.** Artifact and metadata byte limits are configurable. `X-Correlation-ID` is validated, generated when absent, returned in the response and persisted in audit events. Error responses do not expose database or stack details.

## Migration policy

`0001_initial.py` remains the historical initial migration. `0002_integrity_corrections.py`, `0003_artifact_version_chain.py`, `0004_project_scoped_integrity.py` and `0005_persistence_compatibility_repairs.py` are additive/incremental. `0002` adds the same-project context predecessor constraint. `0003` adds the server-derived version number, predecessor fields, legacy compatibility marker, composite foreign key, chain checks, explicit version uniqueness, immutability triggers and supporting index. `0004` adds project-scoped association columns, composite foreign keys for approvals, artifact lineage and decision evidence, and PostgreSQL immutability triggers. `0005` repairs databases that already recorded `0004` before the final trigger set or the composite context predecessor constraint was present. It validates cross-project and orphaned predecessors before changing constraints, installs only missing triggers, and is idempotent against a fully repaired database. The chain was validated on isolated PostgreSQL databases in Docker; production deployment remains outside this increment.

## Consequences

Positive consequences:

- A module output can be traced to exact immutable bytes, metadata, parent artifacts and decisions.
- Approval replay and approval reuse are rejected at the service boundary.
- Context and audit history can be reconstructed without relying on mutable JSON projections.
- A future object-storage implementation can replace the local store behind the same port.

Trade-offs and limits:

- Orphaned local bytes may require a later reconciliation/retention job if a database transaction fails after storage succeeds.
- Legacy rows require an explicit, separately approved compatibility migration before their logical identities can continue in the strict chain.

- Authentication, complete multi-user authorization, orchestration and provider integrations remain outside this increment.
- SQLite tests validate local ORM behavior only; the official migration and integration engine is PostgreSQL. PostgreSQL locking, migration execution and production DDL require an explicitly provisioned isolated test environment.

## Reversibility of project-scoped integrity

The `0004` downgrade is a schema reversal, not a lossless data rollback. It
drops the derived `project_id` columns from `artifact_lineage` and
`decision_artifact_evidence`. The values can be reconstructed from the child
artifact or decision only while the referenced rows remain and the same-project
invariant still holds. The downgrade must therefore not be used on a
data-bearing environment as if it preserved every physical column value; any
such action requires an explicit approval and retention decision.

The `0005` downgrade is deliberately conservative: it moves Alembic back to
`0004` but retains the repaired composite predecessor constraint and
immutability triggers. Removing those objects would reopen cross-project writes
or history mutation on databases that required the compatibility repair. The
next upgrade to `0005` is idempotent and does not delete business rows.

Databases already marked `0004` must still execute `alembic upgrade head` so
`0005` can inspect and repair their actual objects. A database with existing
cross-project or orphaned context predecessors is rejected before constraint
changes; operators must resolve those records through an approved data
correction or restore a known-good backup rather than allowing the migration to
reassign them silently.
