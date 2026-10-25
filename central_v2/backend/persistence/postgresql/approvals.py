"""Occurrence revisions and append-only approval decisions."""

from __future__ import annotations

from uuid import UUID, uuid4

from psycopg import Connection
from psycopg.types.json import Jsonb

from .db import transaction


class ApprovalRepository:
    def __init__(self, conn: Connection):
        self.conn = conn

    def occurrence(self, page_id: UUID, first_seen_run_id: UUID,
                    source_key: str | None = None, occurrence_id: UUID | None = None) -> UUID:
        identity = occurrence_id or uuid4()
        with transaction(self.conn):
            self.conn.execute(
                "INSERT INTO fominha.occurrences(occurrence_id,source_page_id,first_seen_run_id,source_occurrence_key) "
                "VALUES(%s,%s,%s,%s)", (identity, page_id, first_seen_run_id, source_key),
            )
        return identity

    def revise_occurrence(self, occurrence_id: UUID, image_version_id: UUID, type_code: str,
                          origin: str, policy_version: str, roi: tuple[float, float, float, float],
                          evidence_version_id: UUID | None = None, candidate: bool = False,
                          source_key: str | None = None, classification: dict | None = None) -> UUID:
        identity = uuid4()
        with transaction(self.conn):
            self.conn.execute("SELECT occurrence_id FROM fominha.occurrences WHERE occurrence_id=%s FOR UPDATE",
                              (occurrence_id,))
            rev = self.conn.execute(
                "SELECT COALESCE(MAX(revision_no),0)+1 FROM fominha.occurrence_revisions WHERE occurrence_id=%s",
                (occurrence_id,),
            ).fetchone()[0]
            self.conn.execute(
                "INSERT INTO fominha.occurrence_revisions(occurrence_revision_id,occurrence_id,revision_no,"
                "evidence_artifact_version_id,reviewed_image_version_id,source_occurrence_key,type_code,origin,"
                "candidate,roi_x,roi_y,roi_width,roi_height,policy_version,classification_json) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (identity, occurrence_id, rev, evidence_version_id, image_version_id, source_key, type_code,
                 origin, candidate, *roi, policy_version, Jsonb(classification or {})),
            )
        return identity

    def approval_batch(self, chapter_id: UUID, check_run_id: UUID, snapshot_version_id: UUID,
                       batch_id: UUID | None = None) -> UUID:
        identity = batch_id or uuid4()
        with transaction(self.conn):
            self.conn.execute(
                "INSERT INTO fominha.approval_batches(approval_batch_id,chapter_id,check_run_id,"
                "source_snapshot_version_id,status) VALUES(%s,%s,%s,%s,'OPEN')",
                (identity, chapter_id, check_run_id, snapshot_version_id),
            )
        return identity

    def approval_subject(self, batch_id: UUID, revision_id: UUID,
                         subject_id: UUID | None = None) -> UUID:
        identity = subject_id or uuid4()
        with transaction(self.conn):
            self.conn.execute(
                "INSERT INTO fominha.approval_subjects(approval_subject_id,approval_batch_id,occurrence_revision_id) "
                "VALUES(%s,%s,%s)", (identity, batch_id, revision_id),
            )
        return identity

    def decide(self, subject_id: UUID, decision: str, image_version_id: UUID,
               policy_version: str, source_snapshot: dict, actor_id: str | None = None,
               reason: str = "") -> tuple[UUID, int]:
        decision_id = uuid4()
        with transaction(self.conn, isolation="SERIALIZABLE"):
            self.conn.execute("SELECT approval_subject_id FROM fominha.approval_subjects "
                              "WHERE approval_subject_id=%s FOR UPDATE", (subject_id,))
            current = self.conn.execute(
                "SELECT d.approval_decision_id,d.decision_seq,c.revision FROM fominha.current_approval_decisions c "
                "JOIN fominha.approval_decisions d USING(approval_subject_id,approval_decision_id) "
                "WHERE c.approval_subject_id=%s FOR UPDATE OF c", (subject_id,),
            ).fetchone()
            previous_id = current[0] if current else None
            sequence = current[1] + 1 if current else 1
            revision = current[2] + 1 if current else 1
            self.conn.execute(
                "INSERT INTO fominha.approval_decisions(approval_decision_id,approval_subject_id,decision_seq,"
                "supersedes_decision_id,decision,actor_id,reason,reviewed_image_version_id,policy_version,source_snapshot) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (decision_id, subject_id, sequence, previous_id, decision, actor_id, reason,
                 image_version_id, policy_version, Jsonb(source_snapshot)),
            )
            if current:
                changed = self.conn.execute(
                    "UPDATE fominha.current_approval_decisions SET approval_decision_id=%s,revision=%s,updated_at=now() "
                    "WHERE approval_subject_id=%s AND revision=%s",
                    (decision_id, revision, subject_id, current[2]),
                ).rowcount
                if changed != 1:
                    raise RuntimeError("approval compare-and-swap conflict")
            else:
                self.conn.execute(
                    "INSERT INTO fominha.current_approval_decisions(approval_subject_id,approval_decision_id,revision) "
                    "VALUES(%s,%s,1)", (subject_id, decision_id),
                )
        return decision_id, sequence

    def add_dependency(self, consumer_version_id: UUID, subject_id: UUID, decision_id: UUID) -> None:
        with transaction(self.conn, isolation="SERIALIZABLE"):
            row = self.conn.execute(
                "SELECT d.decision FROM fominha.current_approval_decisions c "
                "JOIN fominha.approval_decisions d USING(approval_subject_id,approval_decision_id) "
                "WHERE c.approval_subject_id=%s AND c.approval_decision_id=%s FOR KEY SHARE OF c",
                (subject_id, decision_id),
            ).fetchone()
            if row is None or row[0] != "APPROVE":
                raise ValueError("artifact requires a current APPROVE decision")
            self.conn.execute(
                "INSERT INTO fominha.approval_dependencies(consumer_version_id,approval_subject_id,required_decision_id) "
                "VALUES(%s,%s,%s)", (consumer_version_id, subject_id, decision_id),
            )
