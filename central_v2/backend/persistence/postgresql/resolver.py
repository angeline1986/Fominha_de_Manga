"""Fail-closed active artifact resolver."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from psycopg import Connection

from .artifact_store import ArtifactStore, StorageReceipt


class ResolutionError(RuntimeError):
    """The requested logical artifact is missing, stale or unverifiable."""


@dataclass(frozen=True)
class ResolvedArtifact:
    artifact_slot_id: UUID
    artifact_version_id: UUID
    sha256: str
    path: Path
    byte_size: int
    revision: int


class ArtifactResolver:
    def __init__(self, conn: Connection, store: ArtifactStore):
        self.conn = conn
        self.store = store

    def resolve_active(self, slot_id: UUID) -> ResolvedArtifact:
        row = self.conn.execute(
            "SELECT a.artifact_version_id,a.revision,o.storage_key,o.sha256,o.byte_size "
            "FROM fominha.active_artifacts a JOIN fominha.artifact_versions v USING(artifact_version_id) "
            "JOIN fominha.artifact_objects o USING(object_id) WHERE a.artifact_slot_id=%s", (slot_id,),
        ).fetchone()
        if row is None:
            raise ResolutionError("no active artifact is registered for this slot")
        version_id, revision, key, sha, byte_size = row
        closure = self.conn.execute(
            "WITH RECURSIVE deps(id) AS (SELECT %s::uuid UNION "
            "SELECT d.input_version_id FROM fominha.artifact_dependencies d JOIN deps x "
            "ON d.consumer_version_id=x.id WHERE d.required) SELECT id FROM deps", (version_id,),
        ).fetchall()
        versions = [item[0] for item in closure]
        placeholders = ",".join(["%s"] * len(versions))
        stale = self.conn.execute(
            "SELECT v.artifact_version_id FROM fominha.artifact_versions v LEFT JOIN LATERAL ("
            "SELECT state FROM fominha.artifact_state_events e WHERE e.artifact_version_id=v.artifact_version_id "
            "ORDER BY sequence_no DESC LIMIT 1) s ON true WHERE v.artifact_version_id IN (" + placeholders + ") "
            "AND s.state IS DISTINCT FROM 'VALID' LIMIT 1", versions,
        ).fetchone()
        if stale:
            raise ResolutionError(f"artifact dependency is not VALID: {stale[0]}")
        stale_dep = self.conn.execute(
            "SELECT d.input_version_id FROM fominha.artifact_dependencies d LEFT JOIN fominha.active_artifacts a "
            "ON a.artifact_slot_id=(SELECT artifact_slot_id FROM fominha.artifact_versions v "
            "WHERE v.artifact_version_id=d.input_version_id) WHERE d.consumer_version_id = ANY(%s) "
            "AND d.required AND a.artifact_version_id IS DISTINCT FROM d.input_version_id LIMIT 1", (versions,),
        ).fetchone()
        if stale_dep:
            raise ResolutionError("an input version is no longer active")
        bad_approval = self.conn.execute(
            "SELECT d.approval_subject_id FROM fominha.approval_dependencies d "
            "LEFT JOIN fominha.current_approval_decisions c USING(approval_subject_id) "
            "LEFT JOIN fominha.approval_decisions a ON a.approval_subject_id=d.approval_subject_id "
            "AND a.approval_decision_id=c.approval_decision_id "
            "WHERE d.consumer_version_id = ANY(%s) AND (c.approval_decision_id IS DISTINCT FROM d.required_decision_id "
            "OR a.decision IS DISTINCT FROM 'APPROVE') LIMIT 1", (versions,),
        ).fetchone()
        if bad_approval:
            raise ResolutionError(f"approval dependency is no longer current: {bad_approval[0]}")
        pending = self.conn.execute(
            "SELECT 1 FROM fominha.invalidation_outbox WHERE status<>'DONE' AND "
            "(previous_version_id = ANY(%s) OR previous_approval_decision_id IN ("
            "SELECT required_decision_id FROM fominha.approval_dependencies WHERE consumer_version_id=ANY(%s))) LIMIT 1",
            (versions, versions),
        ).fetchone()
        if pending:
            raise ResolutionError("invalidation is pending; resolution fails closed")
        receipt: StorageReceipt = self.store.verify(key, expected_sha256=sha)
        if receipt.byte_size != byte_size:
            raise ResolutionError("stored object size differs from PostgreSQL metadata")
        return ResolvedArtifact(slot_id, version_id, sha, receipt.path, byte_size, revision)
