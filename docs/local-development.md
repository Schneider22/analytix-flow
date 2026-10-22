# Local Development

## Current prerequisites

The intended runtime uses Python, FastAPI, SQLAlchemy, Alembic, a PostgreSQL driver, PostgreSQL and Docker Compose. Dependencies are declared in `backend/requirements.txt` but are not installed automatically by this repository change.

## Environment

Copy `.env.example` to `.env` and replace local-only values if required. Do not commit `.env`, real credentials or production connection strings.

For the supported Docker Compose path:

```text
docker compose up --build
```

The API is then available at `http://localhost:8000` and health is checked at `http://localhost:8000/api/v1/health`.

## Migrations

From the `backend` directory, with the project dependencies installed:

```text
alembic upgrade head
```

The current migration head is `0003_artifact_version_chain`. The initial migration is intentionally retained unchanged; the correction migrations add artifact storage/version integrity, explicit lineage/evidence, typed approval scope, context predecessors and the mandatory server-derived artifact version chain. Historical artifacts are preserved as `legacy_version` when their predecessor cannot be inferred without inventing data.

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

The automated API tests create an isolated temporary SQLite database because the current environment does not provide a PostgreSQL driver or active Docker daemon. PostgreSQL integration tests and runtime migration execution are not claimed as executed until those prerequisites are available. The concurrency test runs only when `ANALYTIXFLOW_TEST_DATABASE_URL` points to an explicitly supplied isolated PostgreSQL test database; it is skipped otherwise.
