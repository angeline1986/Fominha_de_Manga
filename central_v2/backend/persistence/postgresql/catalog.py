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
            row = self.conn.execute(
                "INSERT INTO fominha.providers(provider_id,code,display_name) VALUES(%s,%s,%s) "
                "ON CONFLICT(code) DO UPDATE SET code=EXCLUDED.code RETURNING provider_id",
                (identity, code, display_name),
            ).fetchone()
        return row[0]

    def work(self, provider_id: UUID, external_key: str, display_name: str,
             work_id: UUID | None = None, status: str = "ACTIVE") -> UUID:
        identity = work_id or uuid4()
        with transaction(self.conn):
            row = self.conn.execute(
                "INSERT INTO fominha.works(work_id,provider_id,external_key,display_name,catalog_status) "
                "VALUES(%s,%s,%s,%s,%s) ON CONFLICT(provider_id,external_key) "
                "DO UPDATE SET external_key=EXCLUDED.external_key RETURNING work_id",
                (identity, provider_id, external_key, display_name, status),
            ).fetchone()
        return row[0]

    def chapter(self, work_id: UUID, chapter_key: str, display_order: int | None = None,
                chapter_id: UUID | None = None) -> UUID:
        identity = chapter_id or uuid4()
        with transaction(self.conn):
            row = self.conn.execute(
                "INSERT INTO fominha.chapters(chapter_id,work_id,chapter_key,display_order) VALUES(%s,%s,%s,%s) "
                "ON CONFLICT(work_id,chapter_key) DO UPDATE SET chapter_key=EXCLUDED.chapter_key "
                "RETURNING chapter_id", (identity, work_id, chapter_key, display_order),
            ).fetchone()
        return row[0]

    def source_page(self, chapter_id: UUID, source_key: str, original_filename: str,
                    display_order: int | None = None, page_id: UUID | None = None) -> UUID:
        identity = page_id or uuid4()
        with transaction(self.conn):
            row = self.conn.execute(
                "INSERT INTO fominha.source_pages(source_page_id,chapter_id,source_key,original_filename,display_order) "
                "VALUES(%s,%s,%s,%s,%s) ON CONFLICT(chapter_id,source_key) "
                "DO UPDATE SET source_key=EXCLUDED.source_key RETURNING source_page_id",
                (identity, chapter_id, source_key, original_filename, display_order),
            ).fetchone()
        return row[0]

    def segment(self, chapter_id: UUID, segment_key: str, segment_id: UUID | None = None) -> UUID:
        identity = segment_id or uuid4()
        with transaction(self.conn):
            row = self.conn.execute(
                "INSERT INTO fominha.derived_segments(segment_id,chapter_id,segment_key) VALUES(%s,%s,%s) "
                "ON CONFLICT(chapter_id,segment_key) DO UPDATE SET segment_key=EXCLUDED.segment_key "
                "RETURNING segment_id", (identity, chapter_id, segment_key),
            ).fetchone()
        return row[0]

    def stage(self, stage_code: str, contract_version: str, display_name: str,
              stage_class: str = "PIPELINE", stage_id: UUID | None = None) -> UUID:
        identity = stage_id or uuid4()
        with transaction(self.conn):
            row = self.conn.execute(
                "INSERT INTO fominha.pipeline_stages(stage_id,stage_code,contract_version,display_name,stage_class) "
                "VALUES(%s,%s,%s,%s,%s) ON CONFLICT(stage_code,contract_version) "
                "DO UPDATE SET stage_code=EXCLUDED.stage_code RETURNING stage_id",
                (identity, stage_code, contract_version, display_name, stage_class),
            ).fetchone()
        return row[0]
