"""Add artifact storage, logical versioning and explicit evidence lineage.

Revision ID: 0002_integrity_corrections
Revises: 0001_initial
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002_integrity_corrections"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "project_context_snapshots",
        sa.Column("predecessor_id", sa.String(length=36), nullable=True),
    )
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("project_context_snapshots", recreate="always") as batch_op:
            batch_op.create_unique_constraint(
                "uq_context_snapshot_project_scoped_id", ["id", "project_id"]
            )
            batch_op.create_foreign_key(
                "fk_context_snapshot_predecessor_project",
                "project_context_snapshots",
                ["predecessor_id", "project_id"],
                ["id", "project_id"],
                ondelete="RESTRICT",
            )
    else:
        op.create_unique_constraint(
            "uq_context_snapshot_project_scoped_id",
            "project_context_snapshots",
            ["id", "project_id"],
        )
        op.create_foreign_key(
            "fk_context_snapshot_predecessor_project",
            "project_context_snapshots",
            "project_context_snapshots",
            ["predecessor_id", "project_id"],
            ["id", "project_id"],
            ondelete="RESTRICT",
        )
    op.create_index(
        "ix_project_context_snapshots_predecessor_id",
        "project_context_snapshots",
        ["predecessor_id"],
    )

    op.add_column("artifacts", sa.Column("logical_id", sa.String(length=128), nullable=True))
    op.add_column("artifacts", sa.Column("storage_id", sa.String(length=36), nullable=True))
    op.execute("UPDATE artifacts SET logical_id = id WHERE logical_id IS NULL")
    if op.get_bind().dialect.name == "sqlite":
        # SQLite requires table recreation for these ALTER TABLE operations.
        with op.batch_alter_table("artifacts", recreate="always") as batch_op:
            batch_op.alter_column("logical_id", existing_type=sa.String(length=128), nullable=False)
            batch_op.create_unique_constraint(
                "uq_artifact_project_logical_version",
                ["project_id", "logical_id", "artifact_version"],
            )
            batch_op.create_unique_constraint("uq_artifact_storage_id", ["storage_id"])
    else:
        # PostgreSQL can alter the existing table in place. Recreating it would
        # attempt to replace artifacts_pkey while approvals.artifact_id still
        # references that key from 0001.
        op.alter_column("artifacts", "logical_id", existing_type=sa.String(length=128), nullable=False)
        op.create_unique_constraint(
            "uq_artifact_project_logical_version",
            "artifacts",
            ["project_id", "logical_id", "artifact_version"],
        )
        op.create_unique_constraint("uq_artifact_storage_id", "artifacts", ["storage_id"])

    op.create_table(
        "artifact_lineage",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("child_artifact_id", sa.String(length=36), nullable=False),
        sa.Column("parent_artifact_id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(["child_artifact_id"], ["artifacts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["parent_artifact_id"], ["artifacts.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("child_artifact_id", "parent_artifact_id", name="uq_artifact_lineage_pair"),
    )
    op.create_index("ix_artifact_lineage_child_artifact_id", "artifact_lineage", ["child_artifact_id"])
    op.create_index("ix_artifact_lineage_parent_artifact_id", "artifact_lineage", ["parent_artifact_id"])

    op.add_column("approvals", sa.Column("scope_type", sa.String(length=32), nullable=True))
    op.add_column("approvals", sa.Column("decision_id", sa.String(length=36), nullable=True))
    op.execute("UPDATE approvals SET scope_type = CASE WHEN artifact_id IS NULL THEN 'project' ELSE 'artifact' END")
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("approvals", recreate="always") as batch_op:
            batch_op.alter_column("scope_type", existing_type=sa.String(length=32), nullable=False)
            batch_op.create_foreign_key(
                "fk_approval_decision",
                "decisions",
                ["decision_id"],
                ["id"],
                ondelete="RESTRICT",
            )
            batch_op.create_check_constraint(
                "ck_approval_scope_shape",
                "(scope_type = 'project' AND artifact_id IS NULL AND artifact_version IS NULL AND execution_id IS NULL) "
                "OR (scope_type = 'artifact' AND artifact_id IS NOT NULL AND artifact_version IS NOT NULL) "
                "OR (scope_type = 'execution' AND execution_id IS NOT NULL)",
            )
    else:
        # Keep PostgreSQL approvals in place as well; it supports all of these
        # operations directly and already has artifact_id -> artifacts.id.
        op.alter_column("approvals", "scope_type", existing_type=sa.String(length=32), nullable=False)
        op.create_foreign_key(
            "fk_approval_decision",
            "approvals",
            "decisions",
            ["decision_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        op.create_check_constraint(
            "ck_approval_scope_shape",
            "approvals",
            "(scope_type = 'project' AND artifact_id IS NULL AND artifact_version IS NULL AND execution_id IS NULL) "
            "OR (scope_type = 'artifact' AND artifact_id IS NOT NULL AND artifact_version IS NOT NULL) "
            "OR (scope_type = 'execution' AND execution_id IS NOT NULL)",
        )

    op.create_table(
        "decision_artifact_evidence",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("decision_id", sa.String(length=36), nullable=False),
        sa.Column("artifact_id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(["decision_id"], ["decisions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["artifact_id"], ["artifacts.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("decision_id", "artifact_id", name="uq_decision_artifact_evidence_pair"),
    )
    op.create_index("ix_decision_artifact_evidence_decision_id", "decision_artifact_evidence", ["decision_id"])
    op.create_index("ix_decision_artifact_evidence_artifact_id", "decision_artifact_evidence", ["artifact_id"])

    # PostgreSQL's initial unnamed FKs receive conventional generated names.
    # The guard is conditional so static SQLite tests do not claim PostgreSQL behavior.
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        project_tables = ("project_context_snapshots", "artifacts", "decisions", "approvals", "audit_events")
        for table_name in project_tables:
            op.execute(f"ALTER TABLE {table_name} DROP CONSTRAINT IF EXISTS {table_name}_project_id_fkey")
            op.execute(
                f"ALTER TABLE {table_name} ADD CONSTRAINT fk_{table_name}_project_restrict "
                "FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE RESTRICT"
            )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        project_tables = ("project_context_snapshots", "artifacts", "decisions", "approvals", "audit_events")
        for table_name in project_tables:
            op.execute(f"ALTER TABLE {table_name} DROP CONSTRAINT IF EXISTS fk_{table_name}_project_restrict")
            op.execute(
                f"ALTER TABLE {table_name} ADD CONSTRAINT {table_name}_project_id_fkey "
                "FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE CASCADE"
            )

    op.drop_index("ix_decision_artifact_evidence_artifact_id", table_name="decision_artifact_evidence")
    op.drop_index("ix_decision_artifact_evidence_decision_id", table_name="decision_artifact_evidence")
    op.drop_table("decision_artifact_evidence")
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("approvals", recreate="always") as batch_op:
            batch_op.drop_constraint("ck_approval_scope_shape", type_="check")
            batch_op.drop_constraint("fk_approval_decision", type_="foreignkey")
            batch_op.drop_column("decision_id")
            batch_op.drop_column("scope_type")
    else:
        op.drop_constraint("ck_approval_scope_shape", "approvals", type_="check")
        op.drop_constraint("fk_approval_decision", "approvals", type_="foreignkey")
        op.drop_column("approvals", "decision_id")
        op.drop_column("approvals", "scope_type")

    op.drop_index("ix_artifact_lineage_parent_artifact_id", table_name="artifact_lineage")
    op.drop_index("ix_artifact_lineage_child_artifact_id", table_name="artifact_lineage")
    op.drop_table("artifact_lineage")
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("artifacts", recreate="always") as batch_op:
            batch_op.drop_constraint("uq_artifact_storage_id", type_="unique")
            batch_op.drop_constraint("uq_artifact_project_logical_version", type_="unique")
            batch_op.drop_column("storage_id")
            batch_op.drop_column("logical_id")
    else:
        op.drop_constraint("uq_artifact_storage_id", "artifacts", type_="unique")
        op.drop_constraint("uq_artifact_project_logical_version", "artifacts", type_="unique")
        op.drop_column("artifacts", "storage_id")
        op.drop_column("artifacts", "logical_id")

    op.drop_index("ix_project_context_snapshots_predecessor_id", table_name="project_context_snapshots")
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("project_context_snapshots", recreate="always") as batch_op:
            batch_op.drop_constraint("fk_context_snapshot_predecessor_project", type_="foreignkey")
            batch_op.drop_constraint("uq_context_snapshot_project_scoped_id", type_="unique")
            batch_op.drop_column("predecessor_id")
    else:
        op.drop_constraint(
            "fk_context_snapshot_predecessor_project",
            "project_context_snapshots",
            type_="foreignkey",
        )
        op.drop_constraint(
            "uq_context_snapshot_project_scoped_id",
            "project_context_snapshots",
            type_="unique",
        )
        op.drop_column("project_context_snapshots", "predecessor_id")
