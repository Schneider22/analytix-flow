from __future__ import annotations

import shutil
from pathlib import Path
from uuid import uuid4

import pytest

from app.storage import (
    ArtifactIntegrityError,
    ArtifactNotFoundError,
    ArtifactStorePathError,
    ArtifactTooLargeError,
    LocalArtifactStore,
)


@pytest.fixture()
def store_dir():
    path = Path(__file__).parents[1] / ".artifact-store-test-runs" / uuid4().hex
    path.mkdir(parents=True, exist_ok=False)
    yield path
    shutil.rmtree(path, ignore_errors=True)


def test_local_store_writes_reads_and_hashes_server_side(store_dir):
    store = LocalArtifactStore(store_dir, max_bytes=1024)
    stored = store.put(b"hello analytixflow")

    assert stored.storage_id
    assert stored.content_hash.startswith("sha256:")
    assert store.read(stored.storage_id, expected_hash=stored.content_hash) == b"hello analytixflow"
    assert store.metadata(stored.storage_id).size_bytes == len(b"hello analytixflow")


def test_local_store_detects_corruption(store_dir):
    store = LocalArtifactStore(store_dir, max_bytes=1024)
    stored = store.put(b"original")
    store._path_for(stored.storage_id).write_bytes(b"tampered")

    with pytest.raises(ArtifactIntegrityError):
        store.read(stored.storage_id)


def test_local_store_deletes_staged_artifact(store_dir):
    store = LocalArtifactStore(store_dir, max_bytes=1024)
    stored = store.put(b"staged")

    store.delete(stored.storage_id)

    with pytest.raises(ArtifactNotFoundError):
        store.read(stored.storage_id)


def test_local_store_rejects_missing_and_traversal_ids(store_dir):
    store = LocalArtifactStore(store_dir, max_bytes=1024)

    with pytest.raises(ArtifactNotFoundError):
        store.read(str(uuid4()))
    with pytest.raises(ArtifactStorePathError):
        store.read("..\\outside")


def test_local_store_enforces_size_limit_and_stays_inside_root(store_dir):
    store = LocalArtifactStore(store_dir, max_bytes=4)

    with pytest.raises(ArtifactTooLargeError):
        store.put(b"12345")
    assert all(path.parent.resolve() == store_dir.resolve() for path in store_dir.iterdir())
