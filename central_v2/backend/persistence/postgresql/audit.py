"""Append-only audit event helpers."""

from __future__ import annotations

from uuid import UUID, uuid4

from psycopg import Connection
from psycopg.types.json import Jsonb

from .db import transaction


class AuditRepository:
    def __init__(self, conn: Connection):
        self.conn = conn

    def append(self, aggregate_type: str, aggregate_id: UUID, event_type: str,
               payload: dict | None = None, actor_id: str | None = None,
               correlation_id: UUID | None = None) -> UUID:
        event_id = uuid4()
        with transaction(self.conn):
            self.conn.execute(
                "INSERT INTO fominha.audit_events(audit_event_id,aggregate_type,aggregate_id,event_type,"
                "actor_id,correlation_id,payload_json) VALUES(%s,%s,%s,%s,%s,%s,%s)",
                (event_id, aggregate_type, aggregate_id, event_type, actor_id,
                 correlation_id, Jsonb(payload or {})),
            )
        return event_id

    def history(self, aggregate_type: str, aggregate_id: UUID) -> list[dict]:
        rows = self.conn.execute(
            "SELECT event_type,actor_id,occurred_at,correlation_id,payload_json FROM fominha.audit_events "
            "WHERE aggregate_type=%s AND aggregate_id=%s ORDER BY occurred_at,audit_event_id",
            (aggregate_type, aggregate_id),
        ).fetchall()
        return [{"event_type": row[0], "actor_id": row[1], "occurred_at": row[2],
                 "correlation_id": row[3], "payload": row[4]} for row in rows]
