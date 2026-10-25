"""Local SHA-256 Artifact Store using atomic create-if-absent publication."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Iterable


class ArtifactConflict(RuntimeError):
    """An existing content key does not contain its claimed bytes."""


@dataclass(frozen=True)
class StorageReceipt:
    sha256: str
    byte_size: int
    storage_key: str
    path: Path
    reused: bool


class ArtifactStore:
    def __init__(self, root: Path | str):
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.objects = self.root / "artifacts" / "sha256"
        self.quarantine = self.root / "quarantine"

    def path_for(self, sha256: str) -> Path:
        if len(sha256) != 64 or any(ch not in "0123456789abcdef" for ch in sha256):
            raise ValueError("sha256 must be lowercase hexadecimal")
        return self.objects / sha256[:2] / sha256[2:4] / sha256

    def put_bytes(self, value: bytes) -> StorageReceipt:
        from io import BytesIO

        return self.put_stream(BytesIO(value))

    def put_file(self, source: Path | str) -> StorageReceipt:
        with Path(source).open("rb") as stream:
            return self.put_stream(stream)

    def put_stream(self, stream: BinaryIO, chunk_size: int = 1024 * 1024) -> StorageReceipt:
        digest = hashlib.sha256()
        size = 0
        temporary: Path | None = None
        key: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(dir=self.root, prefix=".staging-", delete=False) as temp:
                temporary = Path(temp.name)
                while chunk := stream.read(chunk_size):
                    digest.update(chunk)
                    size += len(chunk)
                    temp.write(chunk)
                temp.flush()
                os.fsync(temp.fileno())
            sha = digest.hexdigest()
            key = self.path_for(sha)
            key.parent.mkdir(parents=True, exist_ok=True)
            os.chmod(temporary, 0o444)
            try:
                os.link(temporary, key)
                self._fsync_dir(key.parent)
                return StorageReceipt(sha, size, self._key(sha), key, False)
            except FileExistsError:
                existing = self.verify(key, expected_sha256=sha)
                if existing.byte_size != size:
                    self._record_conflict(sha, size, existing.byte_size)
                    raise ArtifactConflict(f"HASH_KEY_CONFLICT for {sha}: size mismatch")
                return StorageReceipt(sha, size, self._key(sha), key, True)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def verify(self, path_or_key: Path | str, expected_sha256: str | None = None) -> StorageReceipt:
        if isinstance(path_or_key, Path):
            path = path_or_key
        elif path_or_key.startswith("sha256/"):
            digest = path_or_key.rsplit("/", 1)[-1]
            path = self.path_for(digest)
            if self._key(digest) != path_or_key:
                raise ValueError("invalid content-addressed storage key")
        else:
            path = self.path_for(path_or_key)
        path = path.resolve(strict=True)
        if not path.is_relative_to(self.objects.resolve()):
            raise ValueError("artifact path escapes configured object root")
        digest = hashlib.sha256()
        size = 0
        with path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
                size += len(chunk)
        actual = digest.hexdigest()
        expected = expected_sha256 or path.name
        if actual != expected:
            self._record_conflict(expected, -1, size)
            raise ArtifactConflict(f"HASH_KEY_CONFLICT for {expected}: observed {actual}")
        return StorageReceipt(actual, size, self._key(actual), path, True)

    def iter_objects(self) -> Iterable[Path]:
        if not self.objects.exists():
            return ()
        return (path for path in self.objects.glob("[0-9a-f][0-9a-f]/[0-9a-f][0-9a-f]/*") if path.is_file())

    def _record_conflict(self, sha: str, expected_size: int, observed_size: int) -> None:
        self.quarantine.mkdir(parents=True, exist_ok=True)
        marker = self.quarantine / f"{sha}-{time.time_ns()}.json"
        payload = json.dumps({"sha256": sha, "expected_size": expected_size,
                              "observed_size": observed_size, "created_ns": time.time_ns()})
        fd = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())

    def _key(self, sha: str) -> str:
        return f"sha256/{sha[:2]}/{sha[2:4]}/{sha}"

    @staticmethod
    def _fsync_dir(directory: Path) -> None:
        fd = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
