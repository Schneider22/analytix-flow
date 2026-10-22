"""Enforce server-derived artifact version predecessor chains.

Revision ID: 0003_artifact_version_chain
Revises: 0002_integrity_corrections
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0003_artifact_version_chain"
down_revision: Union[str, None] = "0002_integrity_corrections"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


CHAIN_CHECK = (
    "(legacy_version IS TRUE AND version_number IS NULL AND predecessor_artifact_id IS NULL "
    "AND predecessor_version_number IS NULL) "
    "OR (legacy_version IS FALSE AND version_number IS NOT NULL AND version_number = 1 "
    "AND predecessor_artifact_id IS NULL AND predecessor_version_number IS NULL) "
    "OR (legacy_version IS FALSE AND version_number IS NOT NULL AND version_number > 1 "
    "AND predecessor_artifact_id IS NOT NULL AND predecessor_version_number = version_number - 1)"
)
LABEL_CHECK = "legacy_version IS TRUE OR artifact_version = ('v' || CAST(version_number AS VARCHAR))"
NOT_SELF_CHECK = "predecessor_artifact_id IS NULL OR predecessor_artifact_id <> id"


def _create_immutability_guards(operation) -> None:
    dialect = operation.get_bind().dialect.name
    if dialect == "sqlite":
        operation.execute(
            "CREATE TRIGGER IF NOT EXISTS trg_artifacts_immutable_update "
            "BEFORE UPDATE ON artifacts BEGIN "
            "SELECT RAISE(ABORT, 'Artifact versions are immutable'); END"
        )
        operation.execute(
            "CREATE TRIGGER IF NOT EXISTS trg_artifacts_immutable_delete "
            "BEFORE DELETE ON artifacts BEGIN "
            "SELECT RAISE(ABORT, 'Artifact versions are immutable'); END"
        )
    elif dialect == "postgresql":
        operation.execute(
            "CREATE OR REPLACE FUNCTION analytixflow_reject_artifact_mutation() "
            "RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN "
            "RAISE EXCEPTION 'Artifact versions are immutable'; END; $$"
        )
        operation.execute("DROP TRIGGER IF EXISTS trg_artifacts_immutable ON artifacts")
        operation.execute(
            "CREATE TRIGGER trg_artifacts_immutable "
            "BEFORE UPDATE OR DELETE ON artifacts FOR EACH ROW "
            "EXECUTE FUNCTION analytixflow_reject_artifact_mutation()"
        )


def _drop_immutability_guards(operation) -> None:
    dialect = operation.get_bind().dialect.name
    if dialect == "sqlite":
        operation.execute("DROP TRIGGER IF EXISTS trg_artifacts_immutable_update")
        operation.execute("DROP TRIGGER IF EXISTS trg_artifacts_immutable_delete")
    elif dialect == "postgresql":
        operation.execute("DROP TRIGGER IF EXISTS trg_artifacts_immutable ON artifacts")
        operation.execute("DROP FUNCTION IF EXISTS analytixflow_reject_artifact_mutation()")


def _add_chain_constraints(operation) -> None:
    operation.alter_column(
        "legacy_version",
        existing_type=sa.Boolean(),
        existing_server_default=sa.true(),
        server_default=sa.false(),
        nullable=False,
    )
    operation.create_unique_constraint(
        "uq_artifact_identity_version_number",
        ["id", "project_id", "logical_id", "version_number"],
    )
    operation.create_unique_constraint(
        "uq_artifact_project_logical_version_number",
        ["project_id", "logical_id", "version_number"],
    )
    operation.create_foreign_key(
        "fk_artifact_predecessor_id",
        "artifacts",
        ["predecessor_artifact_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    operation.create_foreign_key(
        "fk_artifact_predecessor_same_identity",
        "artifacts",
        ["predecessor_artifact_id", "project_id", "logical_id", "predecessor_version_number"],
        ["id", "project_id", "logical_id", "version_number"],
        ondelete="RESTRICT",
    )
    operation.create_check_constraint("ck_artifact_version_chain_shape", CHAIN_CHECK)
    operation.create_check_constraint("ck_artifact_version_label_matches_number", LABEL_CHECK)
    operation.create_check_constraint("ck_artifact_predecessor_not_self", NOT_SELF_CHECK)


def _drop_chain_constraints(operation) -> None:
    operation.drop_constraint("ck_artifact_predecessor_not_self", type_="check")
    operation.drop_constraint("ck_artifact_version_label_matches_number", type_="check")
    operation.drop_constraint("ck_artifact_version_chain_shape", type_="check")
    operation.drop_constraint("fk_artifact_predecessor_same_identity", type_="foreignkey")
    operation.drop_constraint("fk_artifact_predecessor_id", type_="foreignkey")
    operation.drop_constraint("uq_artifact_project_logical_version_number", type_="unique")
    operation.drop_constraint("uq_artifact_identity_version_number", type_="unique")


def upgrade() -> None:
    # Existing rows have no unambiguous predecessor chain in the historical
    # schema. Preserve them as explicitly marked legacy rows rather than
    # inventing links or changing their content.
    op.add_column("artifacts", sa.Column("version_number", sa.Integer(), nullable=True))
    op.add_column(
        "artifacts",
        sa.Column("legacy_version", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column("artifacts", sa.Column("predecessor_artifact_id", sa.String(length=36), nullable=True))
    op.add_column("artifacts", sa.Column("predecessor_version_number", sa.Integer(), nullable=True))
    op.execute(
        "UPDATE artifacts SET legacy_version = TRUE, version_number = NULL, "
        "predecessor_artifact_id = NULL, predecessor_version_number = NULL"
    )

    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("artifacts", recreate="always") as batch_op:
            _add_chain_constraints(batch_op)
    else:
        _add_chain_constraints(op)

    op.create_index(
        "ix_artifacts_predecessor_artifact_id",
        "artifacts",
        ["predecessor_artifact_id"],
    )
    _create_immutability_guards(op)


def downgrade() -> None:
    _drop_immutability_guards(op)
    op.drop_index("ix_artifacts_predecessor_artifact_id", table_name="artifacts")
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("artifacts", recreate="always") as batch_op:
            _drop_chain_constraints(batch_op)
            batch_op.drop_column("predecessor_version_number")
            batch_op.drop_column("predecessor_artifact_id")
            batch_op.drop_column("legacy_version")
            batch_op.drop_column("version_number")
    else:
        _drop_chain_constraints(op)
        op.drop_column("predecessor_version_number", table_name="artifacts")
        op.drop_column("predecessor_artifact_id", table_name="artifacts")
        op.drop_column("legacy_version", table_name="artifacts")
        op.drop_column("version_number", table_name="artifacts")
