"""Read-only metadata/blob reconciliation. No orphan is deleted automatically."""

from __future__ import annotations

from psycopg import Connection

from .artifact_store import ArtifactConflict, ArtifactStore


def reconcile_store(conn: Connection, store: ArtifactStore) -> list[dict]:
    rows = conn.execute("SELECT storage_key,sha256,byte_size FROM fominha.artifact_objects").fetchall()
    registered = {row[0]: (row[1], row[2]) for row in rows}
    report = []
    seen = set()
    for key, (sha, byte_size) in registered.items():
        try:
            receipt = store.verify(key, expected_sha256=sha)
            if receipt.byte_size != byte_size:
                report.append({"storage_key": key, "status": "CORRUPT", "reason": "size mismatch"})
            else:
                seen.add(key)
        except (OSError, ArtifactConflict, ValueError) as exc:
            report.append({"storage_key": key, "status": "MISSING_OR_CORRUPT", "reason": str(exc)})
    for path in store.iter_objects():
        key = f"sha256/{path.relative_to(store.objects).as_posix()}"
        if key not in registered:
            try:
                receipt = store.verify(path, expected_sha256=path.name)
                report.append({"storage_key": key, "sha256": receipt.sha256,
                               "status": "ORPHAN_CANDIDATE"})
            except (OSError, ArtifactConflict, ValueError) as exc:
                report.append({"storage_key": key, "status": "QUARANTINE_REVIEW", "reason": str(exc)})
    return report
