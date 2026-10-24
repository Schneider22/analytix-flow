# Local Development

## Current prerequisites

The intended runtime uses Python, FastAPI, SQLAlchemy, Alembic, a PostgreSQL driver, PostgreSQL and Docker Compose. Dependencies are declared in `backend/requirements.txt` and are installed by the backend Dockerfile. The contract tests require the declared `jsonschema` and `referencing` packages; missing packages fail the validation test instead of being silently skipped.

PostgreSQL is the supported migration and integration-test engine. SQLite is
used only by the isolated application smoke tests that create the schema from
SQLAlchemy metadata; the full Alembic chain is not currently supported on
SQLite because the historical correction migration contains PostgreSQL-style
constraint operations outside a SQLite batch context. Do not use SQLite runs
as evidence that PostgreSQL migrations or concurrency are valid.

## Environment

Copy `.env.example` to `.env` and replace local-only values if required. Do not commit `.env`, real credentials or production connection strings.

For the supported Docker Compose path, build the image and apply migrations as
an explicit, reviewable step before starting the API:

```text
docker compose build api
docker compose up -d db
docker compose run --rm --no-deps api alembic upgrade head
docker compose up api
```

The API container does not run Alembic automatically at startup. This prevents
an application restart from changing a database without an explicit migration
command.

The API is then available at `http://localhost:8000` and health is checked at `http://localhost:8000/api/v1/health`.

## Migrations

From the `backend` directory, with the project dependencies installed:

```text
alembic upgrade head
```

The current migration head is `0005_persistence_compat` (file
`0005_persistence_compatibility_repairs.py`). The initial migration is intentionally retained unchanged; the correction migrations add artifact storage/version integrity, explicit project-scoped lineage/evidence, typed approval scope, context predecessors and the mandatory server-derived artifact version chain. Migration 0005 repairs databases that already recorded 0004 before the composite context predecessor constraint or the complete PostgreSQL trigger set was present. Historical artifacts are preserved as `legacy_version` when their predecessor cannot be inferred without inventing data.

The migration reads `DATABASE_URL` from the environment through `backend/alembic/env.py`.

## Direct backend execution

```text
cd backend
uvicorn app.main:app --reload
```

If `DATABASE_URL` is absent in development, the application uses a local SQLite fallback for smoke testing. PostgreSQL remains the intended persistence target and should be used for integration verification.

## Tests

```text
cd backend
pytest
```

The automated API tests create an isolated temporary SQLite database. PostgreSQL
integrity tests use only `ANALYTIXFLOW_TEST_DATABASE_URL` and allow the explicit
isolated databases `analytixflow_test` or `analytixflow_migration_check`.
Concurrency tests use the separate
`ANALYTIXFLOW_CONCURRENCY_DATABASE_URL`, whose only allowed destination is
`analytixflow_concurrency_test`. Both helpers require the URL database, the
connected database and the `public` schema to match the allowlist, and only
allow local hosts (`127.0.0.1`, `localhost`, `::1`) or the Docker Compose
service name `db`. They never create or drop tables, delete rows or target the
primary `analytixflow` database. The concurrency database is intentionally
separate because artifact immutability prevents safe destructive cleanup after
committed concurrent writes. If a required URL is absent, the corresponding
tests are skipped with an explicit prerequisite message; if the destination is
reachable but wrong or unmigrated, the tests fail rather than silently
skipping.

### Preparing the PostgreSQL test database

The test database must be created explicitly and separately from `analytixflow`. With the development PostgreSQL container running, create it without deleting data or volumes:

```text
docker compose exec db psql -U analytixflow -d analytixflow -v ON_ERROR_STOP=1 -c "CREATE DATABASE analytixflow_test"
```

If it already exists, do not recreate it. Build the backend image after dependency changes, then apply migrations only to the test database by overriding `DATABASE_URL` for the one-off command. `alembic upgrade head` is required even when the database already reports 0004 so that 0005 can inspect and repair its actual constraints and triggers:

```text
docker compose build api
docker compose run --rm --no-deps -e DATABASE_URL=postgresql+psycopg://analytixflow:change-me-local-only@db:5432/analytixflow_test api alembic upgrade head
```

Prepare the dedicated concurrency database separately, without reusing the
primary or integrity-test databases:

```text
docker compose exec db psql -U analytixflow -d analytixflow -v ON_ERROR_STOP=1 -c "CREATE DATABASE analytixflow_concurrency_test"
docker compose run --rm --no-deps -e DATABASE_URL=postgresql+psycopg://analytixflow:change-me-local-only@db:5432/analytixflow_concurrency_test api alembic upgrade head
```

For tests executed from the host, set `ANALYTIXFLOW_TEST_DATABASE_URL` to the host-published endpoint:

```text
$env:ANALYTIXFLOW_TEST_DATABASE_URL = "postgresql+psycopg://analytixflow:change-me-local-only@127.0.0.1:5432/analytixflow_test"
$env:ANALYTIXFLOW_CONCURRENCY_DATABASE_URL = "postgresql+psycopg://analytixflow:change-me-local-only@127.0.0.1:5432/analytixflow_concurrency_test"
$env:ANALYTIXFLOW_CONCURRENCY_EXPECTED_DATABASE = "analytixflow_concurrency_test"
pytest tests/test_project_scoped_integrity_postgres.py tests/test_concurrency.py
```

These commands never target the primary `analytixflow` database for migration
execution and do not remove volumes or databases. If Docker, PostgreSQL or the
declared dependencies are unavailable, report the corresponding tests as
pending rather than substituting SQLite.

### Downgrade data policy

The `0004` downgrade removes the derived `project_id` columns from
`artifact_lineage` and `decision_artifact_evidence`. Their values are
reconstructible only while the referenced artifacts and decisions remain and
the project-consistency invariant holds: lineage can be rebuilt from the child
artifact, and evidence from the decision. The downgrade therefore preserves
the relationship rows but is not a data-preserving reversal of those derived
columns. Do not use it as a rollback on a data-bearing environment without an
explicit approval and backup/retention decision. A later upgrade reruns the
consistency preflight and aborts if the relationships became ambiguous.

### Policy for historical migration repairs

Changes to the implementation of an existing migration, including a downgrade
bug fix, are admissible only before that migration has been distributed to or
applied in a shared environment. For this MVP, the project owner confirmed
that `0002` and `0003` have not been distributed externally, so the current
pre-publication corrections are admissible. Before the first publication,
freeze these revision files and record their checksums. If either revision is
ever published, preserve the historical files and ship a new compatibility
migration or separately versioned repair procedure instead of rewriting the
published history.

The committed implementation of `0002_integrity_corrections.py` failed while
building a fresh PostgreSQL database because its forced batch recreation tried
to replace `artifacts_pkey` while `approvals_artifact_id_fkey` depended on it.
The current pre-publication version performs the PostgreSQL changes in place.
The current `0003_artifact_version_chain.py` uses explicit PostgreSQL operation
signatures and separate batch signatures for SQLite ORM smoke contexts. The
`0005_persistence_compatibility_repairs.py` migration is the forward-compatible
repair for databases that already recorded 0004; it must not be replaced by
editing a revision that those databases have already marked as applied.

For a database already at 0004, verify the target name and run:

```text
docker compose run --rm --no-deps -e DATABASE_URL=postgresql+psycopg://analytixflow:change-me-local-only@db:5432/analytixflow_test api alembic upgrade head
docker compose run --rm --no-deps -e DATABASE_URL=postgresql+psycopg://analytixflow:change-me-local-only@db:5432/analytixflow_test api alembic current
```

The expected revision is `0005_persistence_compat`. If the
preflight reports cross-project or orphaned context predecessors, stop and
resolve them through an approved correction or restore; do not delete or
reassign rows to make the migration pass. The primary `analytixflow` database
must not be used for this validation procedure.
