"""Logical artifact metadata, versions, outputs and dependency edges."""

from __future__ import annotations

from uuid import UUID, uuid4

from psycopg import Connection
from psycopg.types.json import Jsonb

from .artifact_store import ArtifactStore, StorageReceipt
from .db import transaction


class ArtifactRepository:
    def __init__(self, conn: Connection, store: ArtifactStore):
        self.conn = conn
        self.store = store

    def create_slot(self, chapter_id: UUID, subject_type: str, stage_id: UUID, role: str,
                    context_key: str = "", source_page_id: UUID | None = None,
                    segment_id: UUID | None = None, slot_id: UUID | None = None) -> UUID:
        identity = slot_id or uuid4()
        with transaction(self.conn):
            self.conn.execute(
                "INSERT INTO fominha.artifact_slots(artifact_slot_id,chapter_id,subject_type,source_page_id,"
                "segment_id,stage_id,role,context_key) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
                (identity, chapter_id, subject_type, source_page_id, segment_id, stage_id, role, context_key),
            )
        return identity

    def create_version(self, slot_id: UUID, data: bytes | None = None, file_path: str | None = None,
                       media_type: str = "application/octet-stream", run_id: UUID | None = None,
                       version_id: UUID | None = None, legacy_path: str | None = None,
                       manifest_fields: dict | None = None) -> tuple[UUID, StorageReceipt]:
        if (data is None) == (file_path is None):
            raise ValueError("provide exactly one of data or file_path")
        receipt = self.store.put_bytes(data) if data is not None else self.store.put_file(file_path)
        identity = version_id or uuid4()
        with transaction(self.conn):
            slot = self.conn.execute(
                "SELECT stage_id FROM fominha.artifact_slots WHERE artifact_slot_id=%s FOR UPDATE", (slot_id,),
            ).fetchone()
            if slot is None:
                raise ValueError("artifact slot does not exist")
            object_id = self._register_object(receipt, media_type)
            version_no = self.conn.execute(
                "SELECT COALESCE(MAX(version_no),0)+1 FROM fominha.artifact_versions WHERE artifact_slot_id=%s",
                (slot_id,),
            ).fetchone()[0]
            self.conn.execute(
                "INSERT INTO fominha.artifact_versions(artifact_version_id,artifact_slot_id,stage_id,stage_run_id,"
                "object_id,version_no,source_legacy_path,manifest_fields_json) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
                (identity, slot_id, slot[0], run_id, object_id, version_no, legacy_path,
                 Jsonb(manifest_fields or {})),
            )
            self.conn.execute(
                "INSERT INTO fominha.artifact_state_events(state_event_id,artifact_version_id,sequence_no,state) "
                "VALUES(%s,%s,1,'STAGED')", (uuid4(), identity),
            )
        return identity, receipt

    def _register_object(self, receipt: StorageReceipt, media_type: str) -> UUID:
        object_id = uuid4()
        self.conn.execute(
            "INSERT INTO fominha.artifact_objects(object_id,sha256,byte_size,media_type,storage_key) "
            "VALUES(%s,%s,%s,%s,%s) ON CONFLICT(sha256) DO NOTHING",
            (object_id, receipt.sha256, receipt.byte_size, media_type, receipt.storage_key),
        )
        row = self.conn.execute(
            "SELECT object_id,byte_size,storage_key FROM fominha.artifact_objects WHERE sha256=%s FOR KEY SHARE",
            (receipt.sha256,),
        ).fetchone()
        if row[1] != receipt.byte_size or row[2] != receipt.storage_key:
            raise RuntimeError("database object metadata conflicts with verified blob")
        return row[0]

    def add_run_artifact(self, run_id: UUID, scope_ordinal: int, version_id: UUID,
                         direction: str, role: str, ordinal: int = 0) -> None:
        with transaction(self.conn):
            self.conn.execute(
                "INSERT INTO fominha.stage_run_artifacts(stage_run_id,scope_ordinal,artifact_version_id,"
                "direction,artifact_role,ordinal) VALUES(%s,%s,%s,%s,%s,%s)",
                (run_id, scope_ordinal, version_id, direction, role, ordinal),
            )

    def add_dependency(self, consumer_id: UUID, input_id: UUID, role: str, required: bool = True) -> None:
        with transaction(self.conn, isolation="SERIALIZABLE"):
            row = self.conn.execute(
                "SELECT o.sha256 FROM fominha.artifact_versions v JOIN fominha.artifact_objects o USING(object_id) "
                "WHERE v.artifact_version_id=%s FOR KEY SHARE OF v", (input_id,),
            ).fetchone()
            if row is None:
                raise ValueError("input artifact version does not exist")
            cycle = self.conn.execute(
                "WITH RECURSIVE downstream(id) AS ("
                "SELECT consumer_version_id FROM fominha.artifact_dependencies WHERE input_version_id=%s "
                "UNION SELECT d.consumer_version_id FROM fominha.artifact_dependencies d "
                "JOIN downstream x ON d.input_version_id=x.id) SELECT 1 FROM downstream WHERE id=%s LIMIT 1",
                (consumer_id, input_id),
            ).fetchone()
            if consumer_id == input_id or cycle:
                raise ValueError("artifact dependency would create a cycle")
            self.conn.execute(
                "INSERT INTO fominha.artifact_dependencies(consumer_version_id,input_version_id,dependency_role,"
                "required,observed_sha256) VALUES(%s,%s,%s,%s,%s)",
                (consumer_id, input_id, role, required, row[0]),
            )

    def validate(self, version_id: UUID, validation_type: str, status: str,
                 validator_version: str, expected_sha256: str | None = None,
                 observed_sha256: str | None = None, details: dict | None = None) -> UUID:
        identity = uuid4()
        with transaction(self.conn):
            self.conn.execute(
                "INSERT INTO fominha.artifact_validations(validation_id,artifact_version_id,validation_type,status,"
                "validator_version,expected_sha256,observed_sha256,details_json) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
                (identity, version_id, validation_type, status, validator_version,
                 expected_sha256, observed_sha256, Jsonb(details or {})),
            )
        return identity

    def set_state(self, version_id: UUID, state: str, cause_event_id: UUID | None = None,
                  details: dict | None = None) -> int:
        with transaction(self.conn):
            current = self.conn.execute(
                "SELECT sequence_no,state FROM fominha.artifact_state_events WHERE artifact_version_id=%s "
                "ORDER BY sequence_no DESC LIMIT 1 FOR UPDATE", (version_id,),
            ).fetchone()
            if current is None:
                raise ValueError("artifact version has no initial state")
            if state == "VALID":
                row = self.conn.execute(
                    "SELECT o.storage_key,o.sha256,o.byte_size FROM fominha.artifact_versions v "
                    "JOIN fominha.artifact_objects o USING(object_id) WHERE v.artifact_version_id=%s",
                    (version_id,),
                ).fetchone()
                receipt = self.store.verify(row[0], expected_sha256=row[1])
                if receipt.byte_size != row[2]:
                    raise ValueError("artifact object byte size does not match metadata")
                self.conn.execute(
                    "INSERT INTO fominha.artifact_validations(validation_id,artifact_version_id,validation_type,"
                    "status,validator_version,expected_sha256,observed_sha256) "
                    "VALUES(%s,%s,'STORE_SHA256','PASS','artifact-store-v1',%s,%s)",
                    (uuid4(), version_id, row[1], receipt.sha256),
                )
            sequence = current[0] + 1
            self.conn.execute(
                "INSERT INTO fominha.artifact_state_events(state_event_id,artifact_version_id,sequence_no,state,"
                "cause_event_id,details_json) VALUES(%s,%s,%s,%s,%s,%s)",
                (uuid4(), version_id, sequence, state, cause_event_id, Jsonb(details or {})),
            )
        return sequence
