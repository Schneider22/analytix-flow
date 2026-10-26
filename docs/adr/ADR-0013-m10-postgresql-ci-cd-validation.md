# ADR-0013: M10 PostgreSQL Real Integration Validation and CI/CD Automation

## Status

Accepted for Increment 10 (M10).

## Context

AnalytixFlow enforces a strict, evidence-based analytical lifecycle under CRISP-DM governance. Increments 1 through 9 delivered the full suite of eight specialized domain modules (M1–M8) and their end-to-end integration (M9).

Currently, the backend test suite consists of 138 automated tests:
- **114 tests** validate API contracts, domain logic, state machines, and relational operations using an in-memory or temporary SQLite database via FastAPI `TestClient`.
- **24 tests** are specialized integration tests designed to validate PostgreSQL-specific guarantees:
  1. Concurrency and row-level locking (`with_for_update=True`) in [`backend/tests/test_concurrency.py`](file:///c:/Users/Jose/Documents/Proyectos_2026/analytix-flow/backend/tests/test_concurrency.py) (2 tests).
  2. Project-scoped compound foreign key integrity, cross-project reference rejection, and PL/pgSQL immutability triggers in [`backend/tests/test_project_scoped_integrity_postgres.py`](file:///c:/Users/Jose/Documents/Proyectos_2026/analytix-flow/backend/tests/test_project_scoped_integrity_postgres.py) (5 tests).
  3. Relational persistence, multi-hop lineage, and atomic rollbacks across individual modules M3 through M8 in:
     - [`backend/tests/test_m3_preparation_postgres.py`](file:///c:/Users/Jose/Documents/Proyectos_2026/analytix-flow/backend/tests/test_m3_preparation_postgres.py) (1 test).
     - [`backend/tests/test_m4_modeling_postgres.py`](file:///c:/Users/Jose/Documents/Proyectos_2026/analytix-flow/backend/tests/test_m4_modeling_postgres.py) (1 test).
     - [`backend/tests/test_m5_evaluation_postgres.py`](file:///c:/Users/Jose/Documents/Proyectos_2026/analytix-flow/backend/tests/test_m5_evaluation_postgres.py) (1 test).
     - [`backend/tests/test_m6_deployment_postgres.py`](file:///c:/Users/Jose/Documents/Proyectos_2026/analytix-flow/backend/tests/test_m6_deployment_postgres.py) (1 test).
     - [`backend/tests/test_m7_governance_postgres.py`](file:///c:/Users/Jose/Documents/Proyectos_2026/analytix-flow/backend/tests/test_m7_governance_postgres.py) (3 tests).
     - [`backend/tests/test_m8_dashboard_postgres.py`](file:///c:/Users/Jose/Documents/Proyectos_2026/analytix-flow/backend/tests/test_m8_dashboard_postgres.py) (4 tests).
  4. End-to-end full CRISP-DM analytical lifecycle, deterministic reproducibility, idempotency replay, and human approval gates under PostgreSQL in [`backend/tests/test_m9_end_to_end_postgres.py`](file:///c:/Users/Jose/Documents/Proyectos_2026/analytix-flow/backend/tests/test_m9_end_to_end_postgres.py) (6 tests).

In the local Windows development environment, these 24 tests are intentionally skipped (`SKIPPED`) by the [`require_migrated_postgres`](file:///c:/Users/Jose/Documents/Proyectos_2026/analytix-flow/backend/tests/postgres_support.py#L57-L199) fixture because:
1. The PostgreSQL driver (`psycopg`) is not installed in the local virtual environment.
2. No PostgreSQL daemon is listening on local port 5432 (`127.0.0.1:5432`).
3. The Docker daemon is not active.
4. The required environment variables (`ANALYTIXFLOW_TEST_DATABASE_URL` and `ANALYTIXFLOW_CONCURRENCY_DATABASE_URL`) are not defined.

While this non-invasive skip mechanism preserves local developer velocity without polluting the workstation or failing builds on machines without database daemons, it creates an architectural gap: the 24 PostgreSQL integration tests have never been executed and validated against a real, migrated PostgreSQL 16 engine in an automated pipeline. Furthermore, the repository lacks a Continuous Integration (CI) workflow in `.github/workflows/`.

## Decision

We establish an automated Continuous Integration (CI/CD) pipeline using **GitHub Actions** and an ephemeral **PostgreSQL 16 service container** to execute and certify the complete test suite (138 tests) with **zero skipped tests** in the automated pipeline, while preserving safe conditional skipping for local development.

### 1. CI/CD Architecture: GitHub Actions Service Container

We implement `.github/workflows/ci.yml` targeting the standard `ubuntu-latest` runner. The workflow defines a native Docker service container running the official `postgres:16` image:
```yaml
services:
  postgres:
    image: postgres:16
    env:
      POSTGRES_USER: analytixflow
      POSTGRES_PASSWORD: change-me-local-only
      POSTGRES_DB: analytixflow_test
    ports:
      - 5432:5432
    options: >-
      --health-cmd pg_isready
      --health-interval 10s
      --health-timeout 5s
      --health-retries 5
```

### 2. Dual Isolated Databases

To prevent test collision and deadlock interference between standard sequential tests and concurrent locking tests, the pipeline provisions two strictly isolated databases:
1. `analytixflow_test`: Primary test database for module integration and end-to-end tests (`test_*_postgres.py`).
2. `analytixflow_concurrency_test`: Dedicated test database for concurrency stress tests (`test_concurrency.py`).

**Security Invariant:** Under no circumstance shall any test database URL reference the primary production database `analytixflow`. The [`require_migrated_postgres`](file:///c:/Users/Jose/Documents/Proyectos_2026/analytix-flow/backend/tests/postgres_support.py#L57-L199) fixture programmatically enforces this rule, immediately failing (`pytest.fail`) if `expected_database == "analytixflow"`.

The secondary database is provisioned during the workflow initialization step using `psql`:
```bash
PGPASSWORD=change-me-local-only psql -h localhost -U analytixflow -d analytixflow_test -c "CREATE DATABASE analytixflow_concurrency_test;"
```

### 3. Dependency Management and Driver Installation

The pipeline runs on Python 3.12 (standard LTS in GitHub Actions) and installs exact dependencies directly from [`backend/requirements.txt`](file:///c:/Users/Jose/Documents/Proyectos_2026/analytix-flow/backend/requirements.txt), including `psycopg[binary]>=3.2,<4`. This ensures that the binary psycopg 3 driver and C libraries are installed and verified in the CI environment without compilation overhead.

### 4. Deterministic Migration Sequence via Alembic

Before executing any tests, Alembic migrations must be applied to both databases up to the canonical revision `0006_m2_ingestion`.

The migration commands explicitly declare the configuration file path (`-c backend/alembic.ini`) and target `DATABASE_URL`:
```bash
# Migrate primary test database
DATABASE_URL=postgresql+psycopg://analytixflow:change-me-local-only@localhost:5432/analytixflow_test \
  alembic -c backend/alembic.ini upgrade head

# Migrate secondary concurrency database
DATABASE_URL=postgresql+psycopg://analytixflow:change-me-local-only@localhost:5432/analytixflow_concurrency_test \
  alembic -c backend/alembic.ini upgrade head
```

This guarantees that both databases contain:
- All 8 required tables.
- All 9 compound project-scoped foreign key and check constraints.
- All 5 PostgreSQL triggers enforcing immutability on snapshots, decisions, audit events, and artifacts.
- Exact Alembic revision `0006_m2_ingestion` in `alembic_version`.

### 5. Deterministic Test Execution Order and Zero-Skip Guarantee

The workflow exports the required connection URLs:
```bash
ANALYTIXFLOW_TEST_DATABASE_URL=postgresql+psycopg://analytixflow:change-me-local-only@localhost:5432/analytixflow_test
ANALYTIXFLOW_CONCURRENCY_DATABASE_URL=postgresql+psycopg://analytixflow:change-me-local-only@localhost:5432/analytixflow_concurrency_test
```

To eliminate the risk of silent skips (where tests pass because they were bypassed), the pipeline enforces a **Zero-Skip Guarantee**:
1. Pytest executes the complete test directory:
   ```bash
   python -m pytest backend/tests/ -v -ra --durations=10
   ```
2. A validation step asserts that the test report contains:
   - Exactly **138 passed tests** (114 SQLite/unit + 24 PostgreSQL integration).
   - Exactly **0 skipped tests**.
   - Exactly **0 failed tests**.
3. If any test is skipped or fails, the CI build is marked as failed.

### 6. Workflow Triggers and Security Posture

1. **Triggers:**
   - `push` to `main`: Ensures every integration on the primary trunk is certified.
   - `pull_request` to `main`: Ensures proposed changes pass all checks before merge.
2. **Permissions:**
   ```yaml
   permissions:
     contents: read
   ```
   Enforces the principle of least privilege. No write, administrative, or secret permissions are granted.
3. **Credentials:**
   Only dummy local credentials (`change-me-local-only`) are used for the ephemeral container, adhering to zero-trust principles. No external secrets or cloud credentials are required.

### 7. Dual Testing Tier Separation (SQLite vs. PostgreSQL)

- **Tier 1 (Local Development / Smoke):** Fast, daemon-less execution using SQLite. Developers can run `pytest backend/tests/test_m9_end_to_end.py` instantly without spinning up PostgreSQL or installing binary drivers.
- **Tier 2 (Continuous Integration / Certification):** Full enterprise certification on PostgreSQL 16. Validates ACID transactions, row-level locks, PL/pgSQL triggers, and foreign keys.

## Alternatives Considered

1. **Mandatory Local PostgreSQL Daemon / Docker Desktop:**
   - *Rejected:* Imposes heavy friction on local developers, breaks lightweight testing on non-Docker environments, and contradicts the project directive of not assuming Docker is installed or active.
2. **SQLite In-Memory Emulation for PostgreSQL Tests:**
   - *Rejected:* SQLite does not support PostgreSQL PL/pgSQL triggers (`CREATE TRIGGER ... EXECUTE FUNCTION`), row-level locks (`SELECT ... FOR UPDATE`), or dialect-specific check constraints. Bypassing real PostgreSQL would create false confidence.
3. **Cloud-Hosted Persistent Test Database (e.g. AWS RDS / Supabase):**
   - *Rejected:* Introduces external network dependencies, recurring cloud costs, latency, secret management risks, and data pollution across parallel PRs. The ephemeral container in GitHub Actions is isolated, cost-free, and hermetic.

## Verifiable Acceptance Criteria for M10

1. `ADR-0013` is formally recorded in `docs/adr/ADR-0013-m10-postgresql-ci-cd-validation.md`.
2. Workflow file `.github/workflows/ci.yml` is implemented, syntactically validated, and committed to `main`.
3. The GitHub Actions workflow executes successfully on GitHub runners, provisioning PostgreSQL 16, creating `analytixflow_test` and `analytixflow_concurrency_test`, applying Alembic migrations, and executing all 138 tests.
4. The CI summary confirms **138 passed, 0 skipped, 0 failed**.
5. Local SQLite and mock tests continue to execute without regression in the local development environment.
6. The rector document `docs/AnalytixFlow.docx` maintains its exact SHA-256 hash.
7. Production code remains completely untouched.

## Consequences

- The platform gains automated, continuous verification of all analytical and database layers on every commit.
- The 24 PostgreSQL integration tests are certified on real database engines rather than left perpetually skipped.
- Code changes that break PostgreSQL constraints, migrations, or concurrency locks will be blocked automatically before merging.
- Local development workflow remains fast, lightweight, and completely decoupled from external database requirements.
