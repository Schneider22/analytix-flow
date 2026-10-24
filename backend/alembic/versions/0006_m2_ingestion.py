"""Persist idempotent execution state for the M2 ingestion boundary.

Revision ID: 0006_m2_ingestion
Revises: 0005_persistence_compat
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0006_m2_ingestion"
down_revision: Union[str, None] = "0005_persistence_compat"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "executions",
        sa.Column("id", sa.String(length=128), primary_key=True),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("module_id", sa.String(length=32), nullable=False),
        sa.Column("contract_version", sa.String(length=32), nullable=False),
        sa.Column("context_snapshot_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("correlation_id", sa.String(length=128), nullable=False),
        sa.Column("input_hash", sa.String(length=71), nullable=False),
        sa.Column("output_hash", sa.String(length=71), nullable=True),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("result_json", sa.JSON(), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name="fk_execution_project", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["context_snapshot_id", "project_id"],
            ["project_context_snapshots.id", "project_context_snapshots.project_id"],
            name="fk_execution_context_project",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "project_id",
            "module_id",
            "idempotency_key",
            name="uq_execution_project_module_idempotency",
        ),
    )
    op.create_index("ix_executions_project_id", "executions", ["project_id"])
    op.create_index("ix_executions_status", "executions", ["status"])


def downgrade() -> None:
    op.drop_index("ix_executions_status", table_name="executions")
    op.drop_index("ix_executions_project_id", table_name="executions")
    op.drop_table("executions")
