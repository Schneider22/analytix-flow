# ADR 0004 Persistence Integrity Corrections

Status: Accepted for Increment 1 correction

## Context

The first Increment 1 review identified integrity gaps at the persistence boundary: artifact bytes had no storage abstraction, logical artifact identity was conflated with a physical row identifier, lineage and decision evidence were represented only as identifier arrays, context versions lacked an explicit predecessor, and approval scope could be supplied without a server-verifiable binding. These gaps would make later CRISP-DM executions, approvals and audit reconstruction ambiguous.

## Decision

Apply the following corrections without implementing the orchestrator, modules M1-M8, frontend, RAG or cloud deployment:

1. **Separate artifact bytes from metadata.** `ArtifactStore` is a provider-neutral port. The MVP implementation is `LocalArtifactStore`, which assigns storage UUIDs, writes bytes and a SHA-256 sidecar atomically, enforces a byte limit, rejects path traversal and verifies content before metadata is committed. PostgreSQL stores metadata, the storage identifier and the verified hash; it does not store the bytes.
2. **Separate logical and physical artifact identity.** `artifact_id` is the project-scoped logical identity and `version_id` is the immutable database row identifier. New versions use `vN`. The database enforces uniqueness for `(project_id, logical_id, artifact_version)` and `(project_id, logical_id, version_number)`; every persisted strict version has a server-verified content hash.
3. **Enforce a server-derived predecessor chain.** The first version is `v1` with no predecessor. For `vN`, the service locks the project row, finds `vN-1` for the same logical identity and stores its physical identifier. A composite foreign key over physical id, project, logical identity and numeric version, plus check constraints, prevents gaps, cross-project links, cross-identity links, self-links and cycles. The client cannot provide the predecessor.
4. **Use explicit relationship tables.** Artifact lineage and decision evidence use foreign-key association tables. The automatically selected predecessor is also represented in artifact lineage. Existing JSON identifier arrays remain compatibility projections only and are not the integrity boundary.
5. **Preserve ambiguous historical rows.** Rows created before the chain migration are marked `legacy_version` and retain their original values. No predecessor is invented. A legacy logical identity cannot be extended by the new service until a separate compatibility migration is approved.
6. **Version context under a project lock.** A context snapshot records `predecessor_id`. The service locks the project row, reads the latest snapshot, assigns the next version and commits the new snapshot and audit event in one transaction.
7. **Make approval scope typed and canonical.** Approval scope is `project`, `artifact` or `execution`. The service validates action-to-scope rules, resolves exact artifact logical identity plus version, derives the canonical scope from server-side values and calculates `scope_hash`. A supplied hash is checked but never trusted. Scope fields are immutable and resolution is one-shot; only resolution fields may change.
8. **Preserve history.** Snapshots, artifacts, decisions and audit events are immutable. Artifact immutability is enforced by both ORM guards and database triggers, so direct SQL cannot rewrite or delete a version. Project deletion is rejected by the ORM and the incremental migration changes project foreign keys to restrictive behavior for PostgreSQL. Archival/deactivation and retention policies remain separate decisions and no physical deletion endpoint is provided.
9. **Bound and trace requests.** Artifact and metadata byte limits are configurable. `X-Correlation-ID` is validated, generated when absent, returned in the response and persisted in audit events. Error responses do not expose database or stack details.

## Migration policy

`0001_initial.py` remains the historical initial migration. `0002_integrity_corrections.py` and `0003_artifact_version_chain.py` are additive/incremental. `0003` adds the server-derived version number, predecessor fields, legacy compatibility marker, composite foreign key, chain checks, explicit version uniqueness, immutability triggers and supporting index. Runtime execution against PostgreSQL remains a verification task because the review environment has no PostgreSQL driver or active database.

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
- SQLite tests validate local behavior, but PostgreSQL locking, migration execution and production DDL still require an explicitly provisioned test environment.
