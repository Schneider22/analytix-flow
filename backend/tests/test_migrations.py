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


def test_alembic_runtime_is_required_for_migration_execution():
    pytest.importorskip("alembic.command")
