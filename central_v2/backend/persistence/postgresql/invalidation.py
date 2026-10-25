"""Idempotent transitive invalidation worker for artifact and approval changes."""

from __future__ import annotations

from uuid import uuid4

from psycopg import Connection

from .db import transaction


def _affected(conn: Connection, event: dict) -> list:
    if event["cause_type"] == "ARTIFACT_POINTER":
        roots = conn.execute(
            "SELECT consumer_version_id FROM fominha.artifact_dependencies WHERE input_version_id=%s",
            (event["previous_version_id"],),
        ).fetchall() if event["previous_version_id"] else []
    else:
        roots = conn.execute(
            "SELECT consumer_version_id FROM fominha.approval_dependencies WHERE required_decision_id=%s",
            (event["previous_approval_decision_id"],),
        ).fetchall() if event["previous_approval_decision_id"] else []
    ids = {row[0] for row in roots}
    frontier = list(ids)
    while frontier:
        rows = conn.execute(
            "SELECT consumer_version_id FROM fominha.artifact_dependencies WHERE input_version_id = ANY(%s)",
            (frontier,),
        ).fetchall()
        new_ids = {row[0] for row in rows} - ids
        ids.update(new_ids)
        frontier = list(new_ids)
    return sorted(ids, key=str)


def _mark_stale(conn: Connection, version_id, cause_id) -> None:
    conn.execute("SELECT artifact_version_id FROM fominha.artifact_versions WHERE artifact_version_id=%s FOR UPDATE",
                 (version_id,))
    row = conn.execute(
        "SELECT sequence_no,state FROM fominha.artifact_state_events WHERE artifact_version_id=%s "
        "ORDER BY sequence_no DESC LIMIT 1", (version_id,),
    ).fetchone()
    if row and row[1] in ("STALE", "INVALID", "QUARANTINED"):
        return
    sequence = (row[0] if row else 0) + 1
    conn.execute(
        "INSERT INTO fominha.artifact_state_events(state_event_id,artifact_version_id,sequence_no,state,cause_event_id) "
        "VALUES(%s,%s,%s,'STALE',%s)", (uuid4(), version_id, sequence, cause_id),
    )


def process_pending(conn: Connection, limit: int = 50) -> dict[str, int]:
    if limit < 1 or limit > 500:
        raise ValueError("limit must be between 1 and 500")
    counts = {"done": 0, "failed": 0, "staled": 0}
    with transaction(conn):
        events = conn.execute(
            "SELECT event_id,cause_type,previous_version_id,previous_approval_decision_id "
            "FROM fominha.invalidation_outbox WHERE status IN ('PENDING','FAILED') "
            "ORDER BY created_at,event_id FOR UPDATE SKIP LOCKED LIMIT %s", (limit,),
        ).fetchall()
        for event_id, cause_type, previous_version, previous_decision in events:
            try:
                with transaction(conn):
                    event = {"cause_type": cause_type, "previous_version_id": previous_version,
                             "previous_approval_decision_id": previous_decision}
                    affected = _affected(conn, event)
                    for version_id in affected:
                        _mark_stale(conn, version_id, event_id)
                    conn.execute("UPDATE fominha.invalidation_outbox SET status='DONE',attempt_count=attempt_count+1,"
                                 "last_error=NULL,processed_at=now() WHERE event_id=%s", (event_id,))
                counts["done"] += 1
                counts["staled"] += len(affected)
            except Exception as exc:
                conn.execute("UPDATE fominha.invalidation_outbox SET status='FAILED',attempt_count=attempt_count+1,"
                             "last_error=%s WHERE event_id=%s", (str(exc)[:1000], event_id))
                counts["failed"] += 1
    return counts
