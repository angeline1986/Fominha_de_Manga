"""Explicit legacy import records; unverified sources stay unverified."""

from uuid import UUID, uuid4

from psycopg import Connection
from psycopg.types.json import Jsonb

from .db import transaction


class LegacyImportRepository:
    def __init__(self, conn: Connection):
        self.conn = conn

    def begin(self, source_root_id: str, fingerprint: str, importer_version: str,
              batch_id: UUID | None = None) -> UUID:
        identity = batch_id or uuid4()
        with transaction(self.conn):
            row = self.conn.execute(
                "INSERT INTO fominha.legacy_import_batches(import_batch_id,source_root_id,fingerprint,"
                "importer_version,status) VALUES(%s,%s,%s,%s,'RUNNING') "
                "ON CONFLICT(source_root_id,fingerprint) DO NOTHING RETURNING import_batch_id",
                (identity, source_root_id, fingerprint, importer_version),
            ).fetchone()
            if row:
                return row[0]
            return self.conn.execute(
                "SELECT import_batch_id FROM fominha.legacy_import_batches "
                "WHERE source_root_id=%s AND fingerprint=%s", (source_root_id, fingerprint),
            ).fetchone()[0]

    def record(self, batch_id: UUID, legacy_path: str, contract_code: str, classification: str,
               sha256: str | None = None, version_id: UUID | None = None,
               issue_code: str | None = None, details: dict | None = None) -> UUID:
        if classification == "VERIFIED" and version_id is None:
            raise ValueError("verified legacy item requires an artifact version")
        if classification == "LEGACY_UNVERIFIED" and version_id is not None:
            raise ValueError("unverified legacy item cannot reference a promoted version")
        identity = uuid4()
        with transaction(self.conn):
            self.conn.execute(
                "INSERT INTO fominha.legacy_import_items(import_item_id,import_batch_id,legacy_path,"
                "legacy_sha256,contract_code,classification,artifact_version_id,issue_code,details_json) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (identity, batch_id, legacy_path, sha256, contract_code, classification,
                 version_id, issue_code, Jsonb(details or {})),
            )
        return identity

    def finish(self, batch_id: UUID, status: str) -> None:
        if status not in ("COMPLETED", "PARTIAL", "FAILED"):
            raise ValueError("invalid legacy import terminal status")
        with transaction(self.conn):
            changed = self.conn.execute(
                "UPDATE fominha.legacy_import_batches SET status=%s,finished_at=now() "
                "WHERE import_batch_id=%s AND status='RUNNING'", (status, batch_id),
            ).rowcount
            if changed != 1:
                raise ValueError("legacy import batch is missing or already finished")
