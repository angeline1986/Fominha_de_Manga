"""Run lifecycle and immutable run input/output relations."""

from __future__ import annotations

from uuid import UUID, uuid4

from psycopg import Connection
from psycopg.types.json import Jsonb

from .db import transaction


class RunRepository:
    def __init__(self, conn: Connection):
        self.conn = conn

    def create(self, stage_id: UUID, run_key: str, fingerprint: str, scope_type: str,
               actor_id: str | None = None, algorithm: str | None = None,
               algorithm_version: str | None = None, parameters: dict | None = None,
               run_id: UUID | None = None) -> UUID:
        identity = run_id or uuid4()
        with transaction(self.conn):
            row = self.conn.execute(
                "INSERT INTO fominha.stage_runs(stage_run_id,stage_id,run_key,request_fingerprint,scope_type,"
                "status,actor_id,algorithm,algorithm_version,parameters_json) VALUES(%s,%s,%s,%s,%s,'CREATED',%s,%s,%s,%s) "
                "ON CONFLICT(stage_id,run_key) DO NOTHING "
                "RETURNING stage_run_id", (identity, stage_id, run_key, fingerprint, scope_type,
                                            actor_id, algorithm, algorithm_version, Jsonb(parameters or {})),
            ).fetchone()
            if row is None:
                existing = self.conn.execute(
                    "SELECT stage_run_id,request_fingerprint FROM fominha.stage_runs "
                    "WHERE stage_id=%s AND run_key=%s", (stage_id, run_key),
                ).fetchone()
                if existing[1] != fingerprint:
                    raise ValueError("idempotency key reused with a different request fingerprint")
                return existing[0]
            self.conn.execute(
                "INSERT INTO fominha.stage_run_events(event_id,stage_run_id,event_type,actor_id) "
                "VALUES(%s,%s,'CREATED',%s)", (uuid4(), row[0], actor_id),
            )
        return row[0]

    def add_scope(self, run_id: UUID, chapter_id: UUID, ordinal: int = 0,
                  source_page_id: UUID | None = None, segment_id: UUID | None = None) -> None:
        with transaction(self.conn):
            self.conn.execute(
                "INSERT INTO fominha.stage_run_scopes(stage_run_id,ordinal,chapter_id,source_page_id,segment_id) "
                "VALUES(%s,%s,%s,%s,%s)", (run_id, ordinal, chapter_id, source_page_id, segment_id),
            )

    def transition(self, run_id: UUID, expected: str, target: str, actor_id: str | None = None,
                   details: dict | None = None) -> None:
        with transaction(self.conn):
            cursor = self.conn.execute(
                "UPDATE fominha.stage_runs SET status=%s,started_at=CASE WHEN %s='RUNNING' "
                "THEN COALESCE(started_at,now()) ELSE started_at END,finished_at=CASE "
                "WHEN %s IN ('SUCCEEDED','FAILED','CANCELLED','INTERRUPTED') THEN now() ELSE NULL END "
                "WHERE stage_run_id=%s AND status=%s",
                (target, target, target, run_id, expected),
            )
            if cursor.rowcount != 1:
                raise ValueError("stage run was concurrently changed or transition is invalid")
            self.conn.execute(
                "INSERT INTO fominha.stage_run_events(event_id,stage_run_id,event_type,actor_id,details_json) "
                "VALUES(%s,%s,%s,%s,%s)", (uuid4(), run_id, target, actor_id, Jsonb(details or {})),
            )
