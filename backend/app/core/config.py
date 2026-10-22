from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    """Runtime configuration loaded from environment variables.

    PostgreSQL is the intended runtime database. The SQLite fallback exists only
    for local smoke tests and direct development without a configured database.
    """

    database_url: str
    app_env: str
    artifact_store_path: Path
    api_prefix: str = "/api/v1"
    max_artifact_bytes: int = 50 * 1024 * 1024
    max_metadata_bytes: int = 256 * 1024
    max_correlation_id_length: int = 128

    @classmethod
    def from_env(cls) -> "Settings":
        app_env = os.getenv("APP_ENV", "development").strip().lower()
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            if app_env not in {"development", "test"}:
                raise RuntimeError("DATABASE_URL is required outside development and test environments")
            database_url = "sqlite:///./analytixflow-dev.db"

        artifact_store_path = Path(
            os.getenv("ARTIFACT_STORE_PATH", "./.local/artifacts")
        ).expanduser()

        def positive_int(name: str, default: int) -> int:
            raw_value = os.getenv(name, str(default))
            try:
                value = int(raw_value)
            except ValueError as exc:
                raise RuntimeError(f"{name} must be a positive integer") from exc
            if value <= 0:
                raise RuntimeError(f"{name} must be a positive integer")
            return value

        return cls(
            database_url=database_url,
            app_env=app_env,
            artifact_store_path=artifact_store_path,
            max_artifact_bytes=positive_int("MAX_ARTIFACT_BYTES", cls.max_artifact_bytes),
            max_metadata_bytes=positive_int("MAX_METADATA_BYTES", cls.max_metadata_bytes),
            max_correlation_id_length=positive_int(
                "MAX_CORRELATION_ID_LENGTH", cls.max_correlation_id_length
            ),
        )
