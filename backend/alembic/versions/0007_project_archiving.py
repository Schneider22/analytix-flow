"""Add logical project archiving state.

Revision ID: 0007_project_archiving
Revises: 0006_m2_ingestion
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0007_project_archiving"
down_revision: Union[str, None] = "0006_m2_ingestion"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ARCHIVE_STATE_CONSTRAINT = "ck_project_archive_state"
ARCHIVE_INDEX = "ix_projects_archived_at"
ARCHIVE_STATE_EXPRESSION = (
    "(status = 'archived' AND archived_at IS NOT NULL AND archived_from_status IS NOT NULL) "
    "OR (status <> 'archived' AND archived_at IS NULL AND archived_from_status IS NULL)"
)


def upgrade() -> None:
    bind = op.get_bind()
    existing_archived = bind.execute(
        sa.text("SELECT COUNT(*) FROM projects WHERE status = 'archived'")
    ).scalar_one()
    if existing_archived:
        raise RuntimeError(
            "Cannot add project archiving columns while projects already use status='archived'"
        )

    op.add_column(
        "projects",
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "projects",
        sa.Column("archived_from_status", sa.String(length=64), nullable=True),
    )
    op.create_check_constraint(
        ARCHIVE_STATE_CONSTRAINT,
        "projects",
        ARCHIVE_STATE_EXPRESSION,
    )
    op.create_index(ARCHIVE_INDEX, "projects", ["archived_at"])


def downgrade() -> None:
    bind = op.get_bind()
    archived_count = bind.execute(
        sa.text("SELECT COUNT(*) FROM projects WHERE archived_at IS NOT NULL")
    ).scalar_one()
    if archived_count:
        raise RuntimeError("Cannot downgrade while archived projects exist")

    op.drop_index(ARCHIVE_INDEX, table_name="projects")
    op.drop_constraint(ARCHIVE_STATE_CONSTRAINT, "projects", type_="check")
    op.drop_column("projects", "archived_from_status")
    op.drop_column("projects", "archived_at")
