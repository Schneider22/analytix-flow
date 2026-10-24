"""Enforce project-scoped artifact relationships.

Revision ID: 0004_project_scoped_integrity
Revises: 0003_artifact_version_chain
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0004_project_scoped_integrity"
down_revision: Union[str, None] = "0003_artifact_version_chain"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PROJECT_ID_TYPE = sa.String(length=36)


def _create_immutability_guards(bind) -> None:
    if bind.dialect.name != "postgresql":
        return

    op.execute(
        """
        CREATE OR REPLACE FUNCTION analytixflow_reject_immutable_record_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'Immutable record mutation is not allowed';
        END;
        $$
        """
    )
    for table_name, trigger_name in (
        ("project_context_snapshots", "trg_project_context_snapshots_immutable"),
        ("decisions", "trg_decisions_immutable"),
        ("audit_events", "trg_audit_events_immutable"),
    ):
        op.execute(f"DROP TRIGGER IF EXISTS {trigger_name} ON {table_name}")
        op.execute(
            f"CREATE TRIGGER {trigger_name} "
            f"BEFORE UPDATE OR DELETE ON {table_name} FOR EACH ROW "
            "EXECUTE FUNCTION analytixflow_reject_immutable_record_mutation()"
        )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION analytixflow_reject_approval_mutation()
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
    op.execute("DROP TRIGGER IF EXISTS trg_approvals_immutable_scope ON approvals")
    op.execute(
        "CREATE TRIGGER trg_approvals_immutable_scope "
        "BEFORE UPDATE OR DELETE ON approvals FOR EACH ROW "
        "EXECUTE FUNCTION analytixflow_reject_approval_mutation()"
    )


def _drop_immutability_guards(bind) -> None:
    if bind.dialect.name != "postgresql":
        return

    for table_name, trigger_name in (
        ("project_context_snapshots", "trg_project_context_snapshots_immutable"),
        ("decisions", "trg_decisions_immutable"),
        ("audit_events", "trg_audit_events_immutable"),
    ):
        op.execute(f"DROP TRIGGER IF EXISTS {trigger_name} ON {table_name}")
    op.execute("DROP TRIGGER IF EXISTS trg_approvals_immutable_scope ON approvals")
    op.execute("DROP FUNCTION IF EXISTS analytixflow_reject_approval_mutation()")
    op.execute("DROP FUNCTION IF EXISTS analytixflow_reject_immutable_record_mutation()")


def _assert_no_cross_project_references(connection) -> None:
    checks = (
        (
            "approvals to artifacts",
            """
            SELECT COUNT(*)
            FROM approvals AS approval
            JOIN artifacts AS artifact ON artifact.id = approval.artifact_id
            WHERE approval.artifact_id IS NOT NULL
              AND approval.project_id <> artifact.project_id
            """,
        ),
        (
            "approvals to decisions",
            """
            SELECT COUNT(*)
            FROM approvals AS approval
            JOIN decisions AS decision ON decision.id = approval.decision_id
            WHERE approval.decision_id IS NOT NULL
              AND approval.project_id <> decision.project_id
            """,
        ),
        (
            "artifact lineage",
            """
            SELECT COUNT(*)
            FROM artifact_lineage AS lineage
            JOIN artifacts AS child ON child.id = lineage.child_artifact_id
            JOIN artifacts AS parent ON parent.id = lineage.parent_artifact_id
            WHERE child.project_id <> parent.project_id
            """,
        ),
        (
            "decision evidence",
            """
            SELECT COUNT(*)
            FROM decision_artifact_evidence AS evidence
            JOIN decisions AS decision ON decision.id = evidence.decision_id
            JOIN artifacts AS artifact ON artifact.id = evidence.artifact_id
            WHERE decision.project_id <> artifact.project_id
            """,
        ),
    )
    for relationship, query in checks:
        count = connection.execute(sa.text(query)).scalar() or 0
        if count:
            raise RuntimeError(
                "0004_project_scoped_integrity aborted: "
                f"{count} existing {relationship} reference(s) cross project boundaries"
            )


def _add_target_uniques(bind) -> None:
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("artifacts", recreate="always") as batch_op:
            batch_op.create_unique_constraint(
                "uq_artifact_project_scoped_id", ["id", "project_id"]
            )
        with op.batch_alter_table("decisions", recreate="always") as batch_op:
            batch_op.create_unique_constraint(
                "uq_decision_project_scoped_id", ["id", "project_id"]
            )
    else:
        op.create_unique_constraint(
            "uq_artifact_project_scoped_id", "artifacts", ["id", "project_id"]
        )
        op.create_unique_constraint(
            "uq_decision_project_scoped_id", "decisions", ["id", "project_id"]
        )


def _add_project_scoped_foreign_keys(bind) -> None:
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("artifact_lineage", recreate="always") as batch_op:
            batch_op.alter_column(
                "project_id", existing_type=PROJECT_ID_TYPE, nullable=False
            )
            batch_op.create_foreign_key(
                "fk_artifact_lineage_child_project",
                "artifacts",
                ["child_artifact_id", "project_id"],
                ["id", "project_id"],
                ondelete="RESTRICT",
            )
            batch_op.create_foreign_key(
                "fk_artifact_lineage_parent_project",
                "artifacts",
                ["parent_artifact_id", "project_id"],
                ["id", "project_id"],
                ondelete="RESTRICT",
            )
        with op.batch_alter_table("decision_artifact_evidence", recreate="always") as batch_op:
            batch_op.alter_column(
                "project_id", existing_type=PROJECT_ID_TYPE, nullable=False
            )
            batch_op.create_foreign_key(
                "fk_decision_evidence_decision_project",
                "decisions",
                ["decision_id", "project_id"],
                ["id", "project_id"],
                ondelete="CASCADE",
            )
            batch_op.create_foreign_key(
                "fk_decision_evidence_artifact_project",
                "artifacts",
                ["artifact_id", "project_id"],
                ["id", "project_id"],
                ondelete="RESTRICT",
            )
    else:
        op.alter_column(
            "artifact_lineage", "project_id", existing_type=PROJECT_ID_TYPE, nullable=False
        )
        op.alter_column(
            "decision_artifact_evidence",
            "project_id",
            existing_type=PROJECT_ID_TYPE,
            nullable=False,
        )
        op.create_foreign_key(
            "fk_artifact_lineage_child_project",
            "artifact_lineage",
            "artifacts",
            ["child_artifact_id", "project_id"],
            ["id", "project_id"],
            ondelete="RESTRICT",
        )
        op.create_foreign_key(
            "fk_artifact_lineage_parent_project",
            "artifact_lineage",
            "artifacts",
            ["parent_artifact_id", "project_id"],
            ["id", "project_id"],
            ondelete="RESTRICT",
        )
        op.create_foreign_key(
            "fk_decision_evidence_decision_project",
            "decision_artifact_evidence",
            "decisions",
            ["decision_id", "project_id"],
            ["id", "project_id"],
            ondelete="CASCADE",
        )
        op.create_foreign_key(
            "fk_decision_evidence_artifact_project",
            "decision_artifact_evidence",
            "artifacts",
            ["artifact_id", "project_id"],
            ["id", "project_id"],
            ondelete="RESTRICT",
        )
        op.create_foreign_key(
            "fk_approval_artifact_project",
            "approvals",
            "artifacts",
            ["artifact_id", "project_id"],
            ["id", "project_id"],
            ondelete="RESTRICT",
        )
        op.create_foreign_key(
            "fk_approval_decision_project",
            "approvals",
            "decisions",
            ["decision_id", "project_id"],
            ["id", "project_id"],
            ondelete="RESTRICT",
        )


def _add_sqlite_approval_foreign_keys() -> None:
    with op.batch_alter_table("approvals", recreate="always") as batch_op:
        batch_op.create_foreign_key(
            "fk_approval_artifact_project",
            "artifacts",
            ["artifact_id", "project_id"],
            ["id", "project_id"],
            ondelete="RESTRICT",
        )
        batch_op.create_foreign_key(
            "fk_approval_decision_project",
            "decisions",
            ["decision_id", "project_id"],
            ["id", "project_id"],
            ondelete="RESTRICT",
        )


def upgrade() -> None:
    bind = op.get_bind()
    _assert_no_cross_project_references(bind)

    op.add_column(
        "artifact_lineage", sa.Column("project_id", PROJECT_ID_TYPE, nullable=True)
    )
    op.add_column(
        "decision_artifact_evidence",
        sa.Column("project_id", PROJECT_ID_TYPE, nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE artifact_lineage "
            "SET project_id = (SELECT project_id FROM artifacts "
            "WHERE artifacts.id = artifact_lineage.child_artifact_id)"
        )
    )
    op.execute(
        sa.text(
            "UPDATE decision_artifact_evidence "
            "SET project_id = (SELECT project_id FROM decisions "
            "WHERE decisions.id = decision_artifact_evidence.decision_id)"
        )
    )

    _add_target_uniques(bind)
    _add_project_scoped_foreign_keys(bind)
    if bind.dialect.name == "sqlite":
        _add_sqlite_approval_foreign_keys()

    op.create_index(
        "ix_artifact_lineage_child_project",
        "artifact_lineage",
        ["child_artifact_id", "project_id"],
    )
    op.create_index(
        "ix_artifact_lineage_parent_project",
        "artifact_lineage",
        ["parent_artifact_id", "project_id"],
    )
    op.create_index(
        "ix_decision_evidence_decision_project",
        "decision_artifact_evidence",
        ["decision_id", "project_id"],
    )
    op.create_index(
        "ix_decision_evidence_artifact_project",
        "decision_artifact_evidence",
        ["artifact_id", "project_id"],
    )
    _create_immutability_guards(bind)


def _drop_project_scoped_foreign_keys(bind) -> None:
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("approvals", recreate="always") as batch_op:
            batch_op.drop_constraint("fk_approval_decision_project", type_="foreignkey")
            batch_op.drop_constraint("fk_approval_artifact_project", type_="foreignkey")
        with op.batch_alter_table("decision_artifact_evidence", recreate="always") as batch_op:
            batch_op.drop_constraint("fk_decision_evidence_artifact_project", type_="foreignkey")
            batch_op.drop_constraint("fk_decision_evidence_decision_project", type_="foreignkey")
            batch_op.drop_column("project_id")
        with op.batch_alter_table("artifact_lineage", recreate="always") as batch_op:
            batch_op.drop_constraint("fk_artifact_lineage_parent_project", type_="foreignkey")
            batch_op.drop_constraint("fk_artifact_lineage_child_project", type_="foreignkey")
            batch_op.drop_column("project_id")
    else:
        for name, table in (
            ("fk_approval_decision_project", "approvals"),
            ("fk_approval_artifact_project", "approvals"),
            ("fk_decision_evidence_artifact_project", "decision_artifact_evidence"),
            ("fk_decision_evidence_decision_project", "decision_artifact_evidence"),
            ("fk_artifact_lineage_parent_project", "artifact_lineage"),
            ("fk_artifact_lineage_child_project", "artifact_lineage"),
        ):
            op.drop_constraint(name, table, type_="foreignkey")
        op.drop_column("decision_artifact_evidence", "project_id")
        op.drop_column("artifact_lineage", "project_id")


def downgrade() -> None:
    bind = op.get_bind()
    _drop_immutability_guards(bind)
    for index_name, table_name in (
        ("ix_decision_evidence_artifact_project", "decision_artifact_evidence"),
        ("ix_decision_evidence_decision_project", "decision_artifact_evidence"),
        ("ix_artifact_lineage_parent_project", "artifact_lineage"),
        ("ix_artifact_lineage_child_project", "artifact_lineage"),
    ):
        op.drop_index(index_name, table_name=table_name)

    _drop_project_scoped_foreign_keys(bind)
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("decisions", recreate="always") as batch_op:
            batch_op.drop_constraint("uq_decision_project_scoped_id", type_="unique")
        with op.batch_alter_table("artifacts", recreate="always") as batch_op:
            batch_op.drop_constraint("uq_artifact_project_scoped_id", type_="unique")
    else:
        op.drop_constraint("uq_decision_project_scoped_id", "decisions", type_="unique")
        op.drop_constraint("uq_artifact_project_scoped_id", "artifacts", type_="unique")

