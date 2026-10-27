from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    load_dotenv = None

logger = logging.getLogger("analytixflow.config")


def _load_dotenv_if_present(env_path: Path | None = None) -> None:
    """Load configuration from a local .env file if present.

    Preserves existing environment variables (override=False).
    Uses python-dotenv if available, falling back to a direct reader.
    Errors during file access or parsing are surfaced explicitly
    without logging sensitive connection strings or secrets.
    """
    if env_path is not None:
        candidates = [env_path]
    else:
        explicit_file = os.getenv("ANALYTIXFLOW_ENV_FILE")
        if explicit_file:
            candidates = [Path(explicit_file)]
        else:
            candidates = [
                Path.cwd() / ".env",
                Path(__file__).resolve().parent.parent.parent / ".env",
                Path(__file__).resolve().parent.parent.parent.parent / ".env",
            ]

    seen: set[Path] = set()
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            resolved = candidate
        if resolved in seen:
            continue
        seen.add(resolved)
        if not candidate.is_file():
            continue

        if load_dotenv is not None:
            try:
                load_dotenv(dotenv_path=candidate, override=False)
                return
            except (OSError, UnicodeDecodeError) as exc:
                logger.warning("Failed to read environment file %s: %s", candidate.name, type(exc).__name__)
                raise RuntimeError(f"Unable to read environment file at {candidate.name}: {type(exc).__name__}") from exc
        else:
            try:
                with candidate.open("r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#") or "=" not in line:
                            continue
                        key, _, val = line.partition("=")
                        key = key.strip()
                        val = val.strip().strip("'\"")
                        if key and key not in os.environ:
                            os.environ[key] = val
                return
            except (OSError, UnicodeDecodeError) as exc:
                logger.warning("Failed to read environment file %s: %s", candidate.name, type(exc).__name__)
                raise RuntimeError(f"Unable to read environment file at {candidate.name}: {type(exc).__name__}") from exc


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
    def from_env(cls, *, env_file: Path | None = None, load_env: bool = True) -> "Settings":
        if load_env:
            _load_dotenv_if_present(env_file)
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
