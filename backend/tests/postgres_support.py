from __future__ import annotations

import os
from collections.abc import Collection

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from app.db.session import build_engine


DATABASE_URL_ENV = "ANALYTIXFLOW_TEST_DATABASE_URL"
EXPECTED_DATABASE_ENV = "ANALYTIXFLOW_EXPECTED_DATABASE"
DEFAULT_EXPECTED_DATABASE = "analytixflow_test"
ALLOWED_TEST_DATABASES = frozenset({"analytixflow_test", "analytixflow_migration_check"})
CONCURRENCY_DATABASE_URL_ENV = "ANALYTIXFLOW_CONCURRENCY_DATABASE_URL"
CONCURRENCY_EXPECTED_DATABASE_ENV = "ANALYTIXFLOW_CONCURRENCY_EXPECTED_DATABASE"
DEFAULT_CONCURRENCY_DATABASE = "analytixflow_concurrency_test"
ALLOWED_CONCURRENCY_DATABASES = frozenset({DEFAULT_CONCURRENCY_DATABASE})
ALLOWED_TEST_HOSTS = frozenset({"127.0.0.1", "localhost", "::1", "db"})
EXPECTED_REVISION = "0005_persistence_compat"

REQUIRED_TABLES = {
    "projects",
    "project_context_snapshots",
    "artifacts",
    "approvals",
    "artifact_lineage",
    "decisions",
    "decision_artifact_evidence",
    "audit_events",
}

REQUIRED_CONSTRAINTS = {
    "uq_context_snapshot_project_scoped_id",
    "fk_context_snapshot_predecessor_project",
    "fk_artifact_predecessor_same_identity",
    "fk_approval_artifact_project",
    "fk_approval_decision_project",
    "fk_artifact_lineage_child_project",
    "fk_artifact_lineage_parent_project",
    "fk_decision_evidence_decision_project",
    "fk_decision_evidence_artifact_project",
}

REQUIRED_TRIGGERS = {
    "trg_artifacts_immutable",
    "trg_project_context_snapshots_immutable",
    "trg_decisions_immutable",
    "trg_audit_events_immutable",
    "trg_approvals_immutable_scope",
}


def require_migrated_postgres(
    *,
    database_url_env: str = DATABASE_URL_ENV,
    expected_database_env: str = EXPECTED_DATABASE_ENV,
    default_expected_database: str = DEFAULT_EXPECTED_DATABASE,
    allowed_databases: Collection[str] = ALLOWED_TEST_DATABASES,
) -> Engine:
    """Return only an explicitly configured, migrated PostgreSQL test engine.

    This helper never creates or drops schemas. Missing local prerequisites are
    reported as skips; an accessible but incorrectly targeted or unmigrated
    database is a test failure so configuration errors cannot be hidden.
    """

    database_url = os.getenv(database_url_env)
    if not database_url:
        pytest.skip(f"requires an isolated PostgreSQL database in {database_url_env}")

    try:
        parsed_url = make_url(database_url)
    except Exception as exc:
        pytest.fail(f"Invalid {database_url_env}: {exc}", pytrace=False)

    if parsed_url.get_backend_name() != "postgresql":
        pytest.fail(
            f"{database_url_env} must use PostgreSQL, not {parsed_url.get_backend_name()!r}",
            pytrace=False,
        )

    host = (parsed_url.host or "").strip().lower().strip("[]")
    if host not in ALLOWED_TEST_HOSTS:
        pytest.fail(
            f"{database_url_env} must target an explicitly allowed local PostgreSQL host; "
            f"found {parsed_url.host!r}",
            pytrace=False,
        )

    expected_database = os.getenv(expected_database_env, default_expected_database)
    if expected_database not in allowed_databases or expected_database == "analytixflow":
        pytest.fail(
            f"{expected_database_env} must be one of {sorted(allowed_databases)!r} "
            "and can never be the primary database 'analytixflow'; "
            f"found {expected_database!r}",
            pytrace=False,
        )
    if parsed_url.database != expected_database:
        pytest.fail(
            f"{database_url_env} URL database must be exactly {expected_database!r}; "
            f"found {parsed_url.database!r}",
            pytrace=False,
        )

    try:
        engine = build_engine(database_url)
    except ModuleNotFoundError as exc:
        pytest.skip(f"PostgreSQL driver unavailable: {exc}")
    keep_engine = False
    try:
        try:
            with engine.connect() as connection:
                database_name, schema_name = connection.execute(
                    text("SELECT current_database(), current_schema()")
                ).one()
                if database_name != expected_database:
                    pytest.fail(
                        f"{database_url_env} targets {database_name!r}; "
                        f"tests require exactly {expected_database!r}",
                        pytrace=False,
                    )
                if schema_name != "public":
                    pytest.fail(
                        f"{database_url_env} must use the public schema; found {schema_name!r}",
                        pytrace=False,
                    )

                table_names = set(inspect(connection).get_table_names())
                missing_tables = sorted(REQUIRED_TABLES - table_names)
                if missing_tables:
                    pytest.fail(
                        "PostgreSQL test database is missing migrated tables: "
                        + ", ".join(missing_tables),
                        pytrace=False,
                    )

                constraint_names = {
                    row[0]
                    for row in connection.execute(
                        text(
                            "SELECT conname FROM pg_constraint "
                            "WHERE connamespace = 'public'::regnamespace"
                        )
                    )
                }
                missing_constraints = sorted(REQUIRED_CONSTRAINTS - constraint_names)
                if missing_constraints:
                    pytest.fail(
                        "PostgreSQL test database is missing required integrity constraints: "
                        + ", ".join(missing_constraints),
                        pytrace=False,
                    )

                trigger_names = {
                    row[0]
                    for row in connection.execute(
                        text(
                            "SELECT trigger.tgname "
                            "FROM pg_trigger AS trigger "
                            "JOIN pg_class AS table_ref ON table_ref.oid = trigger.tgrelid "
                            "JOIN pg_namespace AS namespace_ref ON namespace_ref.oid = table_ref.relnamespace "
                            "WHERE namespace_ref.nspname = 'public' AND NOT trigger.tgisinternal"
                        )
                    )
                }
                missing_triggers = sorted(REQUIRED_TRIGGERS - trigger_names)
                if missing_triggers:
                    pytest.fail(
                        "PostgreSQL test database is missing required integrity triggers: "
                        + ", ".join(missing_triggers),
                        pytrace=False,
                    )

                revisions = connection.execute(
                    text("SELECT version_num FROM alembic_version ORDER BY version_num")
                ).scalars().all()
                if revisions != [EXPECTED_REVISION]:
                    pytest.fail(
                        "PostgreSQL test database must have exactly Alembic revision "
                        f"{EXPECTED_REVISION!r}; found {revisions!r}",
                        pytrace=False,
                    )
        except ModuleNotFoundError as exc:
            pytest.skip(f"PostgreSQL driver unavailable: {exc}")
        except OperationalError as exc:
            pytest.skip(f"PostgreSQL test database unavailable: {exc}")
        except SQLAlchemyError as exc:
            pytest.fail(f"Could not inspect the PostgreSQL test schema: {exc}", pytrace=False)

        keep_engine = True
        return engine
    finally:
        if not keep_engine:
            engine.dispose()
