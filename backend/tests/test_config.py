from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from app.core.config import Settings, _load_dotenv_if_present


def test_settings_preserves_existing_environment_variables(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@host:5432/primary_db")
    monkeypatch.setenv("APP_ENV", "development")

    env_file = tmp_path / ".env"
    env_file.write_text("DATABASE_URL=sqlite:///overridden.db\nAPP_ENV=test\nNEW_KEY=from_file\n", encoding="utf-8")

    settings = Settings.from_env(env_file=env_file)

    # Precedence must be preserved
    assert settings.database_url == "postgresql+psycopg://user:pass@host:5432/primary_db"
    assert settings.app_env == "development"
    assert os.getenv("NEW_KEY") == "from_file"


def test_settings_loads_from_env_file_when_not_in_environ(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)

    env_file = tmp_path / ".env"
    env_file.write_text("DATABASE_URL=postgresql+psycopg://test:test@127.0.0.1:5432/file_db\nAPP_ENV=development\n", encoding="utf-8")

    settings = Settings.from_env(env_file=env_file)

    assert settings.database_url == "postgresql+psycopg://test:test@127.0.0.1:5432/file_db"
    assert settings.app_env == "development"


def test_settings_fallback_to_sqlite_in_development(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("APP_ENV", "development")

    settings = Settings.from_env(load_env=False)

    assert settings.database_url == "sqlite:///./analytixflow-dev.db"


def test_settings_requires_database_url_in_production(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("APP_ENV", "production")

    with pytest.raises(RuntimeError, match="DATABASE_URL is required outside development and test"):
        Settings.from_env(load_env=False)


def test_settings_validates_positive_integers(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///test.db")
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("MAX_ARTIFACT_BYTES", "-5")

    with pytest.raises(RuntimeError, match="MAX_ARTIFACT_BYTES must be a positive integer"):
        Settings.from_env(load_env=False)


def test_dotenv_loader_surfaces_io_errors(tmp_path: Path):
    env_file = tmp_path / ".env"
    env_file.write_text("DATABASE_URL=secret\n", encoding="utf-8")

    with patch.object(Path, "open", side_effect=PermissionError("Access denied")):
        with patch("app.core.config.load_dotenv", side_effect=OSError("Access denied")):
            with pytest.raises(RuntimeError) as exc_info:
                _load_dotenv_if_present(env_file)

            assert "Unable to read environment file" in str(exc_info.value)
            # Ensure no secrets leaked in exception message
            assert "secret" not in str(exc_info.value)
