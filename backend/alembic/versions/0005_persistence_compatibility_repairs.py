"""Repair integrity objects on databases that already recorded revision 0004.

Revision ID: 0005_persistence_compat
Revises: 0004_project_scoped_integrity
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0005_persistence_compat"
down_revision: Union[str, None] = "0004_project_scoped_integrity"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_CONTEXT_TABLE = "project_context_snapshots"
_CONTEXT_UNIQUE = "uq_context_snapshot_project_scoped_id"
_CONTEXT_FK = "fk_context_snapshot_predecessor_project"

_TRIGGERS = (
    ("artifacts", "trg_artifacts_immutable", "analytixflow_reject_artifact_mutation"),
    (
        "project_context_snapshots",
        "trg_project_context_snapshots_immutable",
        "analytixflow_reject_immutable_record_mutation",
    ),
    ("decisions", "trg_decisions_immutable", "analytixflow_reject_immutable_record_mutation"),
    ("audit_events", "trg_audit_events_immutable", "analytixflow_reject_immutable_record_mutation"),
    ("approvals", "trg_approvals_immutable_scope", "analytixflow_reject_approval_mutation"),
)


def _require_postgresql(bind) -> None:
    if bind.dialect.name != "postgresql":
        raise RuntimeError(
            "0005_persistence_compat requires PostgreSQL; "
            "SQLite is not an official Alembic migration engine"
        )


def _assert_no_incompatible_context_rows(connection) -> None:
    checks = (
        (
            "cross-project context predecessors",
            """
            SELECT COUNT(*)
            FROM project_context_snapshots AS child
            JOIN project_context_snapshots AS predecessor
              ON predecessor.id = child.predecessor_id
            WHERE child.predecessor_id IS NOT NULL
              AND child.project_id <> predecessor.project_id
            """,
        ),
        (
            "orphaned context predecessors",
            """
            SELECT COUNT(*)
            FROM project_context_snapshots AS child
            LEFT JOIN project_context_snapshots AS predecessor
              ON predecessor.id = child.predecessor_id
            WHERE child.predecessor_id IS NOT NULL
              AND predecessor.id IS NULL
            """,
        ),
    )
    for description, query in checks:
        count = connection.execute(sa.text(query)).scalar() or 0
        if count:
            raise RuntimeError(
                "0005_persistence_compat aborted before schema changes: "
                f"{count} {description} detected"
            )


def _context_constraint_state(connection) -> dict[str, object]:
    rows = connection.execute(
        sa.text(
            """
            SELECT c.conname, c.contype, pg_get_constraintdef(c.oid) AS definition
            FROM pg_constraint AS c
            JOIN pg_class AS table_ref ON table_ref.oid = c.conrelid
            JOIN pg_namespace AS namespace_ref ON namespace_ref.oid = table_ref.relnamespace
            WHERE namespace_ref.nspname = 'public'
              AND table_ref.relname = :table_name
              AND c.conname IN (:unique_name, :foreign_key_name)
            """
        ),
        {
            "table_name": _CONTEXT_TABLE,
            "unique_name": _CONTEXT_UNIQUE,
            "foreign_key_name": _CONTEXT_FK,
        },
    ).mappings().all()
    by_name = {row["conname"]: row for row in rows}

    unique = by_name.get(_CONTEXT_UNIQUE)
    if unique is not None:
        expected = "UNIQUE (id, project_id)"
        if unique["contype"] != "u" or expected not in unique["definition"]:
            raise RuntimeError(
                f"0005 found incompatible constraint {_CONTEXT_UNIQUE!r}: "
                f"{unique['definition']}"
            )

    foreign_key = by_name.get(_CONTEXT_FK)
    if foreign_key is not None:
        expected = "FOREIGN KEY (predecessor_id, project_id)"
        if foreign_key["contype"] != "f" or expected not in foreign_key["definition"]:
            raise RuntimeError(
                f"0005 found incompatible constraint {_CONTEXT_FK!r}: "
                f"{foreign_key['definition']}"
            )

    simple_foreign_keys = connection.execute(
        sa.text(
            """
            SELECT c.conname
            FROM pg_constraint AS c
            WHERE c.conrelid = 'public.project_context_snapshots'::regclass
              AND c.confrelid = 'public.project_context_snapshots'::regclass
              AND c.contype = 'f'
              AND c.conkey = ARRAY[
                    (SELECT a.attnum
                     FROM pg_attribute AS a
                     WHERE a.attrelid = c.conrelid
                       AND a.attname = 'predecessor_id')
                  ]::smallint[]
              AND c.confkey = ARRAY[
                    (SELECT a.attnum
                     FROM pg_attribute AS a
                     WHERE a.attrelid = c.confrelid
                       AND a.attname = 'id')
                  ]::smallint[]
            """
        )
    ).scalars().all()
    return {
        "unique_exists": unique is not None,
        "foreign_key_exists": foreign_key is not None,
        "simple_foreign_keys": simple_foreign_keys,
    }


def _trigger_state(connection) -> dict[str, tuple[str, str] | None]:
    state: dict[str, tuple[str, str] | None] = {}
    for table_name, trigger_name, function_name in _TRIGGERS:
        row = connection.execute(
            sa.text(
                """
                SELECT pg_get_triggerdef(trigger.oid) AS definition,
                       trigger.tgenabled AS enabled
                FROM pg_trigger AS trigger
                JOIN pg_class AS table_ref ON table_ref.oid = trigger.tgrelid
                JOIN pg_namespace AS namespace_ref ON namespace_ref.oid = table_ref.relnamespace
                WHERE namespace_ref.nspname = 'public'
                  AND table_ref.relname = :table_name
                  AND trigger.tgname = :trigger_name
                  AND NOT trigger.tgisinternal
                """
            ),
            {"table_name": table_name, "trigger_name": trigger_name},
        ).mappings().first()
        if row is None:
            state[trigger_name] = None
            continue
        if row["enabled"] != "O" or function_name not in row["definition"]:
            raise RuntimeError(
                f"0005 found incompatible trigger {trigger_name!r} on {table_name!r}: "
                f"{row['definition']}"
            )
        state[trigger_name] = (row["definition"], row["enabled"])
    return state


def _repair_context_constraints(bind, state: dict[str, object]) -> None:
    for constraint_name in state["simple_foreign_keys"]:
        op.drop_constraint(constraint_name, _CONTEXT_TABLE, type_="foreignkey")

    if not state["unique_exists"]:
        op.create_unique_constraint(
            _CONTEXT_UNIQUE,
            _CONTEXT_TABLE,
            ["id", "project_id"],
        )

    if not state["foreign_key_exists"]:
        op.create_foreign_key(
            _CONTEXT_FK,
            _CONTEXT_TABLE,
            _CONTEXT_TABLE,
            ["predecessor_id", "project_id"],
            ["id", "project_id"],
            ondelete="RESTRICT",
        )


def _repair_immutability_functions() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.analytixflow_reject_artifact_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'Artifact versions are immutable';
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.analytixflow_reject_immutable_record_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'Immutable record mutation is not allowed';
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.analytixflow_reject_approval_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'Approvals cannot be deleted';
            END IF;

            IF OLD.id IS DISTINCT FROM NEW.id
               OR OLD.project_id IS DISTINCT FROM NEW.project_id
               OR OLD.action IS DISTINCT FROM NEW.action
               OR OLD.scope_type IS DISTINCT FROM NEW.scope_type
               OR OLD.artifact_id IS DISTINCT FROM NEW.artifact_id
               OR OLD.artifact_version IS DISTINCT FROM NEW.artifact_version
               OR OLD.execution_id IS DISTINCT FROM NEW.execution_id
               OR OLD.decision_id IS DISTINCT FROM NEW.decision_id
               OR OLD.scope_hash IS DISTINCT FROM NEW.scope_hash
               OR OLD.requested_by IS DISTINCT FROM NEW.requested_by
               OR OLD.created_at IS DISTINCT FROM NEW.created_at
            THEN
                RAISE EXCEPTION 'Approval scope cannot be changed after creation';
            END IF;

            IF OLD.status IS DISTINCT FROM 'pending'
               AND (OLD.status IS DISTINCT FROM NEW.status
                    OR OLD.resolved_by IS DISTINCT FROM NEW.resolved_by
                    OR OLD.reason IS DISTINCT FROM NEW.reason
                    OR OLD.resolved_at IS DISTINCT FROM NEW.resolved_at)
            THEN
                RAISE EXCEPTION 'Resolved approvals cannot be changed';
            END IF;

            RETURN NEW;
        END;
        $$
        """
    )


def _repair_immutability_triggers(trigger_state: dict[str, tuple[str, str] | None]) -> None:
    for table_name, trigger_name, function_name in _TRIGGERS:
        if trigger_state[trigger_name] is not None:
            continue
        op.execute(
            f"CREATE TRIGGER {trigger_name} "
            f"BEFORE UPDATE OR DELETE ON public.{table_name} FOR EACH ROW "
            f"EXECUTE FUNCTION public.{function_name}()"
        )


def upgrade() -> None:
    bind = op.get_bind()
    _require_postgresql(bind)
    connection = bind

    # All checks happen before any DROP/CREATE operation. PostgreSQL DDL is
    # transactional, but this explicit ordering also gives a clear diagnostic.
    _assert_no_incompatible_context_rows(connection)
    context_state = _context_constraint_state(connection)
    trigger_state = _trigger_state(connection)
    _repair_context_constraints(bind, context_state)
    _repair_immutability_functions()
    _repair_immutability_triggers(trigger_state)


def downgrade() -> None:
    bind = op.get_bind()
    _require_postgresql(bind)

    # This compatibility repair is intentionally conservative. Removing the
    # repaired FK or immutability triggers would reopen cross-project writes or
    # allow history mutation on a database that previously lacked the objects.
    # The Alembic revision can move back to 0004, but the stronger objects stay
    # in place and the next upgrade is idempotent. No business rows are deleted.
    pass
