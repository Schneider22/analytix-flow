import pathlib

import pytest


def test_initial_migration_file_is_present():
    migration = pathlib.Path(__file__).parents[1] / "alembic" / "versions" / "0001_initial.py"
    assert migration.is_file()
    text = migration.read_text(encoding="utf-8")
    assert "def upgrade" in text
    assert "def downgrade" in text


def test_integrity_correction_migration_is_present_and_incremental():
    migration = pathlib.Path(__file__).parents[1] / "alembic" / "versions" / "0002_integrity_corrections.py"
    text = migration.read_text(encoding="utf-8")
    assert migration.is_file()
    assert 'down_revision: Union[str, None] = "0001_initial"' in text
    assert "artifact_lineage" in text
    assert "decision_artifact_evidence" in text
    assert "predecessor_id" in text
    assert "uq_context_snapshot_project_scoped_id" in text
    assert "fk_context_snapshot_predecessor_project" in text


def test_postgresql_check_constraint_declares_table_and_condition():
    migration = pathlib.Path(__file__).parents[1] / "alembic" / "versions" / "0002_integrity_corrections.py"
    text = migration.read_text(encoding="utf-8")
    assert (
        'op.create_check_constraint(\n'
        '            "ck_approval_scope_shape",\n'
        '            "approvals",\n'
    ) in text


def test_artifact_version_chain_migration_is_present_and_incremental():
    migration = pathlib.Path(__file__).parents[1] / "alembic" / "versions" / "0003_artifact_version_chain.py"
    text = migration.read_text(encoding="utf-8")
    assert migration.is_file()
    assert 'down_revision: Union[str, None] = "0002_integrity_corrections"' in text
    assert "version_number" in text
    assert "predecessor_artifact_id" in text
    assert "fk_artifact_predecessor_same_identity" in text
    assert "uq_artifact_project_logical_version_number" in text
    assert "trg_artifacts_immutable" in text
    assert "legacy_version" in text


def test_artifact_version_chain_uses_dialect_specific_constraint_signatures():
    migration = pathlib.Path(__file__).parents[1] / "alembic" / "versions" / "0003_artifact_version_chain.py"
    text = migration.read_text(encoding="utf-8")
    assert "_add_chain_constraints(batch_op, batch=True)" in text
    assert "_add_chain_constraints(op, batch=False)" in text
    assert 'operation.create_check_constraint("ck_artifact_version_chain_shape", "artifacts", CHAIN_CHECK)' in text
    assert 'operation.create_check_constraint("ck_artifact_version_label_matches_number", "artifacts", LABEL_CHECK)' in text
    assert 'operation.create_check_constraint("ck_artifact_predecessor_not_self", "artifacts", NOT_SELF_CHECK)' in text
    assert 'operation.drop_constraint(name, "artifacts", type_=constraint_type)' in text


def test_project_scoped_integrity_migration_is_incremental():
    migration = pathlib.Path(__file__).parents[1] / "alembic" / "versions" / "0004_project_scoped_integrity.py"
    text = migration.read_text(encoding="utf-8")
    assert migration.is_file()
    assert 'revision: str = "0004_project_scoped_integrity"' in text
    assert 'down_revision: Union[str, None] = "0003_artifact_version_chain"' in text
    assert 'sa.Column("project_id", PROJECT_ID_TYPE, nullable=True)' in text
    assert "fk_approval_artifact_project" in text
    assert "fk_artifact_lineage_parent_project" in text
    assert "fk_decision_evidence_artifact_project" in text
    assert "_assert_no_cross_project_references" in text
    assert "trg_project_context_snapshots_immutable" in text
    assert "trg_decisions_immutable" in text
    assert "trg_audit_events_immutable" in text
    assert "trg_approvals_immutable_scope" in text


def test_project_scoped_downgrade_uses_drop_column_table_then_column_signature():
    migration = pathlib.Path(__file__).parents[1] / "alembic" / "versions" / "0004_project_scoped_integrity.py"
    text = migration.read_text(encoding="utf-8")
    assert 'op.drop_column("decision_artifact_evidence", "project_id")' in text
    assert 'op.drop_column("artifact_lineage", "project_id")' in text
    assert 'op.drop_column("project_id", table_name=' not in text


def test_persistence_compatibility_migration_is_incremental_and_non_destructive():
    migration = pathlib.Path(__file__).parents[1] / "alembic" / "versions" / "0005_persistence_compatibility_repairs.py"
    text = migration.read_text(encoding="utf-8")
    assert migration.is_file()
    assert 'revision: str = "0005_persistence_compat"' in text
    assert 'down_revision: Union[str, None] = "0004_project_scoped_integrity"' in text
    assert "_assert_no_incompatible_context_rows" in text
    assert "_context_constraint_state" in text
    assert "_trigger_state" in text
    assert "CREATE OR REPLACE FUNCTION" in text
    assert "CREATE TRIGGER" in text
    assert "DROP SCHEMA" not in text.upper()
    assert "CASCADE" not in text.upper()
    assert "No business rows are deleted" in text


def test_m2_execution_migration_is_incremental_and_project_scoped():
    migration = pathlib.Path(__file__).parents[1] / "alembic" / "versions" / "0006_m2_ingestion.py"
    text = migration.read_text(encoding="utf-8")
    assert migration.is_file()
    assert 'revision: str = "0006_m2_ingestion"' in text
    assert 'down_revision: Union[str, None] = "0005_persistence_compat"' in text
    assert 'op.create_table(\n        "executions"' in text
    assert "fk_execution_context_project" in text
    assert "uq_execution_project_module_idempotency" in text
    assert "op.drop_table(\"executions\")" in text


def test_historical_postgresql_downgrades_use_drop_column_table_then_column_signature():
    migration_0002 = pathlib.Path(__file__).parents[1] / "alembic" / "versions" / "0002_integrity_corrections.py"
    text_0002 = migration_0002.read_text(encoding="utf-8")
    assert 'op.drop_column("approvals", "decision_id")' in text_0002
    assert 'op.drop_column("approvals", "scope_type")' in text_0002
    assert 'op.drop_column("artifacts", "storage_id")' in text_0002
    assert 'op.drop_column("artifacts", "logical_id")' in text_0002
    assert 'op.drop_column("decision_id", table_name=' not in text_0002
    assert 'op.drop_column("scope_type", table_name=' not in text_0002
    assert 'op.drop_column("storage_id", table_name=' not in text_0002
    assert 'op.drop_column("logical_id", table_name=' not in text_0002

    migration_0003 = pathlib.Path(__file__).parents[1] / "alembic" / "versions" / "0003_artifact_version_chain.py"
    text_0003 = migration_0003.read_text(encoding="utf-8")
    for column_name in (
        "predecessor_version_number",
        "predecessor_artifact_id",
        "legacy_version",
        "version_number",
    ):
        assert f'op.drop_column("artifacts", "{column_name}")' in text_0003
        assert f'op.drop_column("{column_name}", table_name=' not in text_0003


def test_alembic_runtime_is_required_for_migration_execution():
    try:
        import alembic.command  # noqa: F401
    except ModuleNotFoundError as exc:
        pytest.fail(
            "Alembic is required for migration validation; install backend/requirements.txt. "
            f"Missing module: {exc.name}",
            pytrace=False,
        )


def test_project_archiving_migration_is_incremental_and_non_destructive():
    migration = pathlib.Path(__file__).parents[1] / "alembic" / "versions" / "0007_project_archiving.py"
    text = migration.read_text(encoding="utf-8")
    assert migration.is_file()
    assert 'revision: str = "0007_project_archiving"' in text
    assert 'down_revision: Union[str, None] = "0006_m2_ingestion"' in text
    assert 'sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True)' in text
    assert 'sa.Column("archived_from_status", sa.String(length=64), nullable=True)' in text
    assert 'ARCHIVE_INDEX = "ix_projects_archived_at"' in text
    assert 'ARCHIVE_STATE_CONSTRAINT = "ck_project_archive_state"' in text
    assert "Cannot downgrade while archived projects exist" in text
    assert "DROP TABLE" not in text.upper()
    assert "DROP SCHEMA" not in text.upper()
