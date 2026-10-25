"""Content manifest for coordinated PostgreSQL and Artifact Store backups."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from psycopg import Connection

from .artifact_store import ArtifactStore


def build_manifest(conn: Connection, store: ArtifactStore) -> dict:
    migration = conn.execute(
        "SELECT version FROM public.fominha_schema_migrations ORDER BY version DESC LIMIT 1"
    ).fetchone()
    objects = conn.execute(
        "SELECT object_id,sha256,byte_size,storage_key FROM fominha.artifact_objects ORDER BY sha256"
    ).fetchall()
    records = []
    for object_id, sha, size, key in objects:
        receipt = store.verify(key, expected_sha256=sha)
        if receipt.byte_size != size:
            raise ValueError(f"blob size does not match metadata: {key}")
        records.append({"object_id": str(object_id), "sha256": sha, "byte_size": size, "storage_key": key})
    active = conn.execute(
        "SELECT artifact_slot_id,artifact_version_id,publication_id,revision "
        "FROM fominha.active_artifacts ORDER BY artifact_slot_id"
    ).fetchall()
    return {"format": 1, "created_at": datetime.now(timezone.utc).isoformat(),
            "schema_version": migration[0] if migration else None, "objects": records,
            "active_artifacts": [{"slot_id": str(row[0]), "version_id": str(row[1]),
                                  "publication_id": str(row[2]), "revision": row[3]} for row in active]}


def write_manifest(path: Path | str, manifest: dict) -> Path:
    target = Path(path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as output:
        output.write(payload)
        output.flush()
        os.fsync(output.fileno())
    directory_fd = os.open(target.parent, os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
    return target


def verify_manifest(manifest: dict, store: ArtifactStore) -> dict[str, int]:
    verified = 0
    for item in manifest.get("objects", []):
        receipt = store.verify(item["storage_key"], expected_sha256=item["sha256"])
        if receipt.byte_size != item["byte_size"]:
            raise ValueError(f"backup object size mismatch: {item['storage_key']}")
        verified += 1
    active = manifest.get("active_artifacts", [])
    if any(not item.get("version_id") or not item.get("slot_id") for item in active):
        raise ValueError("backup manifest contains an empty active version")
    return {"objects_verified": verified, "active_slots": len(active)}
