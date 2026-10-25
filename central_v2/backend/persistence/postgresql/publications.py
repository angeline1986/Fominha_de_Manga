"""Transactional publication and active pointer compare-and-swap."""

from __future__ import annotations

from uuid import UUID, uuid4

from psycopg import Connection
from psycopg.errors import UniqueViolation
from psycopg.types.json import Jsonb

from .artifact_store import ArtifactStore
from .db import transaction
from .reset import record_reset


class PublicationConflict(RuntimeError):
    pass


class PublicationRepository:
    def __init__(self, conn: Connection, store: ArtifactStore):
        self.conn = conn
        self.store = store

    def publish(self, chapter_id: UUID, run_id: UUID, items: list[dict], idempotency_key: str,
                fingerprint: str, actor_id: str | None = None, reason: str = "",
                reset: dict | None = None) -> tuple[UUID, str]:
        if not items:
            raise ValueError("publication must contain at least one item")
        ordered = sorted(items, key=lambda item: str(item["slot_id"]))
        publication_id = uuid4()
        with transaction(self.conn, isolation="SERIALIZABLE"):
            self._verify_objects(ordered)
            existing = self.conn.execute(
                "SELECT publication_id,request_fingerprint,status FROM fominha.publications "
                "WHERE chapter_id=%s AND idempotency_key=%s FOR UPDATE", (chapter_id, idempotency_key),
            ).fetchone()
            if existing:
                if existing[1] != fingerprint:
                    raise PublicationConflict("idempotency key reused with a different fingerprint")
                return existing[0], existing[2]
            run = self.conn.execute("SELECT status FROM fominha.stage_runs WHERE stage_run_id=%s FOR KEY SHARE",
                                    (run_id,)).fetchone()
            if run is None or run[0] != "SUCCEEDED":
                raise ValueError("only a successful run can publish")
            self.conn.execute(
                "INSERT INTO fominha.publications(publication_id,chapter_id,stage_run_id,status,"
                "expected_active_revision,idempotency_key,request_fingerprint,actor_id,reason,publication_type) "
                "VALUES(%s,%s,%s,'STAGED',0,%s,%s,%s,%s,%s)",
                (publication_id, chapter_id, run_id, idempotency_key, fingerprint, actor_id, reason,
                 "RESET" if reset is not None else "PUBLISH"),
            )
            self.conn.execute("SELECT artifact_slot_id FROM fominha.artifact_slots WHERE artifact_slot_id=ANY(%s) "
                              "ORDER BY artifact_slot_id FOR UPDATE", ([item["slot_id"] for item in ordered],))
            valid, failure = self._preflight(chapter_id, run_id, ordered, is_reset=reset is not None)
            if not valid:
                self.conn.execute("UPDATE fominha.publications SET status='ABORTED',reason=%s WHERE publication_id=%s",
                                  (failure, publication_id))
                return publication_id, "ABORTED"
            for item in ordered:
                current = self.conn.execute(
                    "SELECT artifact_version_id,revision FROM fominha.active_artifacts "
                    "WHERE artifact_slot_id=%s FOR UPDATE", (item["slot_id"],),
                ).fetchone()
                current_revision = current[1] if current else 0
                if current_revision != item["expected_revision"]:
                    self.conn.execute("UPDATE fominha.publications SET status='CONFLICT',reason=%s "
                                      "WHERE publication_id=%s", ("active revision changed", publication_id))
                    return publication_id, "CONFLICT"
                self._insert_item(publication_id, chapter_id, item,
                                  current[0] if current else None)
            try:
                with transaction(self.conn):
                    self.conn.execute("UPDATE fominha.publications SET status='COMMITTED',committed_at=now() "
                                      "WHERE publication_id=%s", (publication_id,))
                    for item in ordered:
                        self._advance_pointer(publication_id, item)
                    if reset is not None:
                        record_reset(self.conn, publication_id, chapter_id, ordered, reset, actor_id)
            except PublicationConflict as exc:
                self.conn.execute("UPDATE fominha.publications SET status='CONFLICT',reason=%s "
                                  "WHERE publication_id=%s", (str(exc), publication_id))
                return publication_id, "CONFLICT"
        return publication_id, "COMMITTED"

    def _verify_objects(self, items: list[dict]) -> None:
        for item in items:
            row = self.conn.execute(
                "SELECT o.storage_key,o.sha256,o.byte_size FROM fominha.artifact_versions v "
                "JOIN fominha.artifact_objects o USING(object_id) WHERE v.artifact_version_id=%s",
                (item["version_id"],),
            ).fetchone()
            if row is None:
                raise ValueError("publication artifact version is missing")
            receipt = self.store.verify(row[0], expected_sha256=row[1])
            if receipt.byte_size != row[2]:
                raise ValueError("publication object size differs from metadata")

    def _preflight(self, chapter_id: UUID, run_id: UUID, items: list[dict],
                   is_reset: bool = False) -> tuple[bool, str]:
        for item in items:
            row = self.conn.execute(
                "SELECT v.stage_run_id,s.chapter_id FROM fominha.artifact_versions v "
                "JOIN fominha.artifact_slots s USING(artifact_slot_id) WHERE v.artifact_version_id=%s "
                "AND v.artifact_slot_id=%s FOR KEY SHARE OF v,s", (item["version_id"], item["slot_id"]),
            ).fetchone()
            if row is None or (row[0] != run_id and not is_reset) or row[1] != chapter_id:
                return False, "output version, run, slot and chapter do not match"
            output = self.conn.execute(
                "SELECT 1 FROM fominha.stage_run_artifacts WHERE stage_run_id=%s AND artifact_version_id=%s "
                "AND direction=%s LIMIT 1", (run_id, item["version_id"], "INPUT" if is_reset else "OUTPUT"),
            ).fetchone()
            if output is None:
                return False, "artifact is not registered on the publishing/reset run"
            state = self.conn.execute(
                "SELECT state FROM fominha.artifact_state_events WHERE artifact_version_id=%s "
                "ORDER BY sequence_no DESC LIMIT 1 FOR UPDATE", (item["version_id"],),
            ).fetchone()
            if state is None or state[0] != "VALID":
                return False, "output is not in VALID state"
            if self.conn.execute(
                "SELECT 1 FROM fominha.artifact_dependencies d LEFT JOIN fominha.active_artifacts a "
                "ON a.artifact_slot_id=(SELECT artifact_slot_id FROM fominha.artifact_versions v "
                "WHERE v.artifact_version_id=d.input_version_id) WHERE d.consumer_version_id=%s AND d.required "
                "AND a.artifact_version_id IS DISTINCT FROM d.input_version_id LIMIT 1",
                (item["version_id"],),
            ).fetchone():
                return False, "required input is not the current active version"
            stale_input = self.conn.execute(
                "SELECT 1 FROM fominha.artifact_dependencies d LEFT JOIN LATERAL (SELECT state "
                "FROM fominha.artifact_state_events e WHERE e.artifact_version_id=d.input_version_id "
                "ORDER BY sequence_no DESC LIMIT 1) s ON true WHERE d.consumer_version_id=%s AND d.required "
                "AND s.state IS DISTINCT FROM 'VALID' LIMIT 1", (item["version_id"],),
            ).fetchone()
            if stale_input:
                return False, "required input artifact is not VALID"
            bad_approval = self.conn.execute(
                "SELECT 1 FROM fominha.approval_dependencies d LEFT JOIN fominha.current_approval_decisions c "
                "USING(approval_subject_id) LEFT JOIN fominha.approval_decisions a "
                "ON a.approval_subject_id=d.approval_subject_id AND a.approval_decision_id=c.approval_decision_id "
                "WHERE d.consumer_version_id=%s AND (c.approval_decision_id IS DISTINCT FROM d.required_decision_id "
                "OR a.decision IS DISTINCT FROM 'APPROVE') LIMIT 1", (item["version_id"],),
            ).fetchone()
            if bad_approval:
                return False, "required approval is no longer current"
            pending = self.conn.execute(
                "SELECT 1 FROM fominha.invalidation_outbox WHERE status<>'DONE' AND previous_version_id IN "
                "(SELECT input_version_id FROM fominha.artifact_dependencies WHERE consumer_version_id=%s) "
                "LIMIT 1", (item["version_id"],),
            ).fetchone()
            if pending:
                return False, "input invalidation is pending"
        return True, ""

    def _insert_item(self, publication_id: UUID, chapter_id: UUID, item: dict, previous) -> None:
        self.conn.execute(
            "INSERT INTO fominha.publication_items(publication_id,chapter_id,artifact_slot_id,artifact_version_id,"
            "previous_version_id,expected_active_revision) VALUES(%s,%s,%s,%s,%s,%s)",
            (publication_id, chapter_id, item["slot_id"], item["version_id"], previous, item["expected_revision"]),
        )

    def _advance_pointer(self, publication_id: UUID, item: dict) -> None:
        slot, version = item["slot_id"], item["version_id"]
        expected = item["expected_revision"]
        if expected == 0:
            try:
                self.conn.execute("INSERT INTO fominha.active_artifacts(artifact_slot_id,artifact_version_id,"
                                  "publication_id,revision) VALUES(%s,%s,%s,1)", (slot, version, publication_id))
            except UniqueViolation as exc:
                raise PublicationConflict("active artifact was concurrently created") from exc
            return
        changed = self.conn.execute(
            "UPDATE fominha.active_artifacts SET artifact_version_id=%s,publication_id=%s,revision=revision+1,"
            "updated_at=now() WHERE artifact_slot_id=%s AND revision=%s",
            (version, publication_id, slot, expected),
        ).rowcount
        if changed != 1:
            raise PublicationConflict("active artifact compare-and-swap failed")
