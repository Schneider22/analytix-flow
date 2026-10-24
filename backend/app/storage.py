from __future__ import annotations

import hashlib
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Protocol
from uuid import UUID, uuid4


class ArtifactStoreError(Exception):
    """Base error for artifact byte storage."""


class ArtifactNotFoundError(ArtifactStoreError, FileNotFoundError):
    """The requested server-generated storage identifier does not exist."""


class ArtifactIntegrityError(ArtifactStoreError):
    """Stored bytes or their sidecar hash failed integrity validation."""


class ArtifactStorePathError(ArtifactStoreError, ValueError):
    """A caller attempted to address a path outside the artifact store."""


class ArtifactTooLargeError(ArtifactStoreError, ValueError):
    """The artifact exceeds the configured byte limit."""


@dataclass(frozen=True)
class StoredArtifact:
    storage_id: str
    content_hash: str
    size_bytes: int
    uri: str


class ArtifactStore(Protocol):
    def put(self, content: bytes | bytearray | BinaryIO) -> StoredArtifact:
        """Persist bytes under a server-generated identifier."""

    def read(self, storage_id: str, *, expected_hash: str | None = None) -> bytes:
        """Read and verify bytes addressed by a server-generated identifier."""

    def metadata(self, storage_id: str) -> StoredArtifact:
        """Return verified metadata without loading the content."""

    def delete(self, storage_id: str) -> None:
        """Remove a staged artifact during compensating cleanup."""


class LocalArtifactStore:
    """Filesystem ArtifactStore with atomic writes and integrity sidecars."""

    _ID_PATTERN = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")

    def __init__(self, root: Path, *, max_bytes: int) -> None:
        if max_bytes <= 0:
            raise ValueError("max_bytes must be positive")
        self.root = Path(root).expanduser().resolve()
        self.max_bytes = max_bytes
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, content: bytes | bytearray | BinaryIO) -> StoredArtifact:
        storage_id = str(uuid4())
        data_path = self._path_for(storage_id)
        hash_path = self._hash_path_for(storage_id)
        temporary_paths: list[Path] = []
        digest = hashlib.sha256()
        size = 0

        try:
            fd, temporary_name = tempfile.mkstemp(prefix=".artifact-", suffix=".tmp", dir=self.root)
            temporary_data = Path(temporary_name)
            temporary_paths.append(temporary_data)
            with os.fdopen(fd, "wb") as handle:
                for chunk in self._chunks(content):
                    size += len(chunk)
                    if size > self.max_bytes:
                        raise ArtifactTooLargeError(f"Artifact exceeds {self.max_bytes} bytes")
                    digest.update(chunk)
                    handle.write(chunk)
                handle.flush()
                os.fsync(handle.fileno())

            content_hash = f"sha256:{digest.hexdigest()}"
            fd, temporary_hash_name = tempfile.mkstemp(prefix=".artifact-hash-", suffix=".tmp", dir=self.root)
            temporary_hash = Path(temporary_hash_name)
            temporary_paths.append(temporary_hash)
            with os.fdopen(fd, "w", encoding="ascii") as handle:
                handle.write(content_hash)
                handle.flush()
                os.fsync(handle.fileno())

            os.replace(temporary_data, data_path)
            os.replace(temporary_hash, hash_path)
            temporary_paths.clear()
            return StoredArtifact(
                storage_id=storage_id,
                content_hash=content_hash,
                size_bytes=size,
                uri=self.uri_for(storage_id),
            )
        finally:
            for temporary_path in temporary_paths:
                try:
                    temporary_path.unlink(missing_ok=True)
                except OSError:
                    pass

    def read(self, storage_id: str, *, expected_hash: str | None = None) -> bytes:
        data_path = self._path_for(storage_id)
        hash_path = self._hash_path_for(storage_id)
        if not data_path.is_file() or not hash_path.is_file():
            raise ArtifactNotFoundError("Stored artifact not found")

        declared_hash = hash_path.read_text(encoding="ascii").strip()
        if expected_hash is not None and expected_hash != declared_hash:
            raise ArtifactIntegrityError("Stored artifact hash does not match the expected hash")

        content = data_path.read_bytes()
        if len(content) > self.max_bytes:
            raise ArtifactTooLargeError(f"Artifact exceeds {self.max_bytes} bytes")
        actual_hash = f"sha256:{hashlib.sha256(content).hexdigest()}"
        if actual_hash != declared_hash:
            raise ArtifactIntegrityError("Stored artifact content is corrupted")
        return content

    def metadata(self, storage_id: str) -> StoredArtifact:
        content = self.read(storage_id)
        declared_hash = f"sha256:{hashlib.sha256(content).hexdigest()}"
        return StoredArtifact(
            storage_id=storage_id,
            content_hash=declared_hash,
            size_bytes=len(content),
            uri=self.uri_for(storage_id),
        )

    def delete(self, storage_id: str) -> None:
        data_path = self._path_for(storage_id)
        hash_path = self._hash_path_for(storage_id)
        data_path.unlink(missing_ok=True)
        hash_path.unlink(missing_ok=True)

    def uri_for(self, storage_id: str) -> str:
        self._validate_storage_id(storage_id)
        return f"local-artifact://{storage_id}"

    def _chunks(self, content: bytes | bytearray | BinaryIO):
        if isinstance(content, (bytes, bytearray)):
            yield bytes(content)
            return
        while True:
            chunk = content.read(1024 * 1024)
            if not chunk:
                break
            if not isinstance(chunk, bytes):
                raise TypeError("Artifact streams must return bytes")
            yield chunk

    def _validate_storage_id(self, storage_id: str) -> None:
        if not isinstance(storage_id, str) or not self._ID_PATTERN.fullmatch(storage_id):
            raise ArtifactStorePathError("Invalid artifact storage identifier")
        try:
            UUID(storage_id)
        except ValueError as exc:
            raise ArtifactStorePathError("Invalid artifact storage identifier") from exc

    def _path_for(self, storage_id: str) -> Path:
        self._validate_storage_id(storage_id)
        path = (self.root / f"{storage_id}.bin").resolve()
        if path.parent != self.root or self.root not in path.parents:
            raise ArtifactStorePathError("Artifact path escapes the configured store")
        return path

    def _hash_path_for(self, storage_id: str) -> Path:
        self._validate_storage_id(storage_id)
        path = (self.root / f"{storage_id}.sha256").resolve()
        if path.parent != self.root or self.root not in path.parents:
            raise ArtifactStorePathError("Artifact hash path escapes the configured store")
        return path
