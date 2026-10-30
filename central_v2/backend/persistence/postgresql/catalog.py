"""Normalized catalog and pipeline stage writes."""

from __future__ import annotations

from uuid import UUID, uuid4

from psycopg import Connection

from .db import transaction


class CatalogRepository:
    def __init__(self, conn: Connection):
        self.conn = conn

    def provider(self, code: str, display_name: str, provider_id: UUID | None = None) -> UUID:
        identity = provider_id or uuid4()
        with transaction(self.conn):
            row = self.conn.execute("SELECT fominha.catalog_provider(%s,%s,%s)",
                                    (code, display_name, identity)).fetchone()
        return row[0]

    def work(self, provider_id: UUID, external_key: str, display_name: str,
             work_id: UUID | None = None, status: str = "ACTIVE") -> UUID:
        identity = work_id or uuid4()
        with transaction(self.conn):
            row = self.conn.execute(
                "SELECT fominha.catalog_work(%s,%s,%s,%s,%s)",
                (provider_id, external_key, display_name, status, identity),
            ).fetchone()
        return row[0]

    def chapter(self, work_id: UUID, chapter_key: str, display_order: int | None = None,
                chapter_id: UUID | None = None) -> UUID:
        identity = chapter_id or uuid4()
        with transaction(self.conn):
            row = self.conn.execute(
                "SELECT fominha.catalog_chapter(%s,%s,%s,%s)",
                (work_id, chapter_key, display_order, identity),
            ).fetchone()
        return row[0]

    def source_page(self, chapter_id: UUID, source_key: str, original_filename: str,
                    display_order: int | None = None, page_id: UUID | None = None) -> UUID:
        identity = page_id or uuid4()
        with transaction(self.conn):
            row = self.conn.execute(
                "SELECT fominha.catalog_source_page(%s,%s,%s,%s,%s)",
                (chapter_id, source_key, original_filename, display_order, identity),
            ).fetchone()
        return row[0]

    def segment(self, chapter_id: UUID, segment_key: str, segment_id: UUID | None = None) -> UUID:
        identity = segment_id or uuid4()
        with transaction(self.conn):
            row = self.conn.execute(
                "SELECT fominha.catalog_segment(%s,%s,%s)",
                (chapter_id, segment_key, identity),
            ).fetchone()
        return row[0]

    def stage(self, stage_code: str, contract_version: str, display_name: str,
              stage_class: str = "PIPELINE", stage_id: UUID | None = None) -> UUID:
        identity = stage_id or uuid4()
        with transaction(self.conn):
            row = self.conn.execute(
                "SELECT fominha.catalog_stage(%s,%s,%s,%s,%s)",
                (stage_code, contract_version, display_name, stage_class, identity),
            ).fetchone()
        return row[0]
