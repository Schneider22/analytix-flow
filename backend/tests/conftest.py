from __future__ import annotations

import shutil
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.api import get_db
from app.core.config import Settings
from app.db.base import Base
from app.db.session import build_engine
from app.main import create_app


@pytest.fixture()
def test_dir():
    path = Path(__file__).parents[1] / ".test-runs" / uuid4().hex
    path.mkdir(parents=True, exist_ok=False)
    yield path
    shutil.rmtree(path, ignore_errors=True)


@pytest.fixture()
def app(test_dir):
    database_url = f"sqlite:///{test_dir / 'test.db'}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    application = create_app(
        Settings(database_url=database_url, app_env="test", artifact_store_path=test_dir / "artifacts"),
        engine=engine,
        session_factory=session_factory,
    )
    yield application
    with engine.connect() as connection:
        if database_url.startswith("sqlite"):
            connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
        Base.metadata.drop_all(connection)
    engine.dispose()


@pytest.fixture()
def client(app):
    with TestClient(app) as test_client:
        yield test_client
