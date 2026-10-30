"""Exercise database guards with direct SQL and the effective runtime role."""

from __future__ import annotations

import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

import psycopg

from persistence.postgresql.approvals import ApprovalRepository
from persistence.postgresql.artifact_store import ArtifactStore
from persistence.postgresql.artifacts import ArtifactRepository
from persistence.postgresql.catalog import CatalogRepository
from persistence.postgresql.legacy import LegacyImportRepository
from persistence.postgresql.runs import RunRepository


class M3SqlBoundaries(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dsn = os.environ.get("FOMINHA_PG_TEST_DSN", "")
        if not cls.dsn:
            raise unittest.SkipTest("set FOMINHA_PG_TEST_DSN to a disposable M3 database")
        with psycopg.connect(cls.dsn) as conn:
            name = conn.execute("SELECT current_database()").fetchone()[0]
            count = conn.execute("SELECT count(*) FROM public.fominha_schema_migrations").fetchone()[0]
            if not name.startswith("fominha_m3_test_") or count != 10:
                raise RuntimeError("run the complete suite against a fresh M3 test database")
        cls.temp = TemporaryDirectory(prefix="fominha-m3-sql-")
        cls.store = ArtifactStore(Path(cls.temp.name) / "objects")

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def _two_page_fixture(self, conn):
        catalog, runs = CatalogRepository(conn), RunRepository(conn)
        artifacts = ArtifactRepository(conn, self.store)
        provider = catalog.provider("sql-boundary", "SQL boundary fixture")
        work = catalog.work(provider, str(uuid4()), "Two pages")
        chapter = catalog.chapter(work, "01")
        stage = catalog.stage("SQL_BOUNDARY", "1", "SQL boundary fixture")
        pages, versions = [], []
        for number in (1, 2):
            page = catalog.source_page(chapter, f"page-{number}", f"page-{number}.png")
            slot = artifacts.create_slot(chapter, "SOURCE_PAGE", stage, "SOURCE", source_page_id=page)
            version, _ = artifacts.create_version(slot, data=f"page-{number}-{uuid4()}".encode())
            pages.append(page)
            versions.append(version)
        run = runs.create(stage, str(uuid4()), "two-page-run", "PAGE")
        runs.add_scope(run, chapter, source_page_id=pages[0])
        return chapter, pages, versions, run

    def test_app_role_is_read_only_including_future_tables(self):
        with psycopg.connect(self.dsn) as conn:
            conn.execute("CREATE TABLE fominha.m3_future_role_probe (id integer)")
            with conn.transaction():
                conn.execute("SET LOCAL ROLE fominha_app")
                self.assertEqual(conn.execute("SELECT current_user").fetchone()[0], "fominha_app")
                tables = conn.execute(
                    "SELECT format('%I.%I',schemaname,tablename) FROM pg_tables "
                    "WHERE schemaname='fominha'"
                ).fetchall()
                for (table,) in tables:
                    self.assertTrue(conn.execute("SELECT has_table_privilege(current_user,%s,'SELECT')",
                                                 (table,)).fetchone()[0], table)
                    for privilege in ("INSERT", "UPDATE", "DELETE", "TRUNCATE"):
                        self.assertFalse(conn.execute(
                            "SELECT has_table_privilege(current_user,%s,%s)",
                            (table, privilege)).fetchone()[0], (table, privilege))
                    self.assertFalse(conn.execute(
                        "SELECT has_any_column_privilege(current_user,%s,'UPDATE')",
                        (table,)).fetchone()[0], table)
                with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    with conn.transaction():
                        conn.execute("INSERT INTO fominha.artifact_state_events DEFAULT VALUES")
                with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    with conn.transaction():
                        conn.execute("INSERT INTO fominha.publications DEFAULT VALUES")
            conn.execute("RESET ROLE")
            conn.execute("DROP TABLE fominha.m3_future_role_probe")

    def test_app_role_uses_catalog_functions_without_table_writes(self):
        with psycopg.connect(self.dsn) as conn:
            owners = conn.execute(
                "SELECT DISTINCT pg_get_userbyid(proowner) FROM pg_proc p "
                "JOIN pg_namespace n ON n.oid=p.pronamespace "
                "WHERE n.nspname='fominha' AND p.proname LIKE 'catalog_%'"
            ).fetchall()
            self.assertEqual(owners, [("fominha_migrator",)])
            with conn.transaction():
                conn.execute("SET LOCAL ROLE fominha_app")
                catalog = CatalogRepository(conn)
                key = str(uuid4())
                provider = catalog.provider("restricted-catalog", "Restricted catalog")
                work = catalog.work(provider, key, "Synthetic work")
                chapter = catalog.chapter(work, "01")
                page = catalog.source_page(chapter, "page-01", "page-01.png")
                segment = catalog.segment(chapter, "segment-01")
                stage = catalog.stage("RESTRICTED_CATALOG", "1", "Restricted catalog")
                self.assertEqual(catalog.work(provider, key, "Synthetic work"), work)
                self.assertEqual(catalog.source_page(chapter, "page-01", "page-01.png"), page)
                self.assertTrue(all((provider, work, chapter, page, segment, stage)))
                self.assertEqual(conn.execute("SELECT current_user").fetchone()[0], "fominha_app")
                with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    with conn.transaction():
                        conn.execute("INSERT INTO fominha.providers(provider_id,code,display_name) "
                                     "VALUES(%s,'direct-denied','Denied')", (uuid4(),))
            with conn.transaction():
                conn.execute("SET LOCAL ROLE fominha_retention")
                with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    with conn.transaction():
                        conn.execute("SELECT fominha.catalog_provider(%s,%s,%s)",
                                     ("wrong-role", "Denied", uuid4()))

    def test_direct_sql_rejects_wrong_page_approval(self):
        with psycopg.connect(self.dsn) as conn:
            chapter, pages, versions, run = self._two_page_fixture(conn)
            approvals = ApprovalRepository(conn)
            with self.assertRaises(psycopg.Error):
                with conn.transaction():
                    approvals.approval_batch(chapter, run, versions[1])
            occurrence = approvals.occurrence(pages[0], run)
            revision = approvals.revise_occurrence(occurrence, versions[0], "TEXT", "MANUAL",
                                                   "policy-1", (0.1, 0.1, 0.2, 0.2))
            batch = approvals.approval_batch(chapter, run, versions[0])
            subject = approvals.approval_subject(batch, revision)
            with self.assertRaises(psycopg.Error):
                with conn.transaction():
                    conn.execute(
                        "INSERT INTO fominha.approval_decisions"
                        "(approval_decision_id,approval_subject_id,decision_seq,decision,reason,"
                        "reviewed_image_version_id,policy_version) "
                        "VALUES(%s,%s,1,'APPROVE','',%s,'policy-1')",
                        (uuid4(), subject, versions[1]))

    def test_approval_subject_must_match_snapshot_page(self):
        with psycopg.connect(self.dsn) as conn:
            chapter, pages, versions, run = self._two_page_fixture(conn)
            approvals = ApprovalRepository(conn)
            occurrence = approvals.occurrence(pages[1], run)
            revision = approvals.revise_occurrence(occurrence, versions[1], "TEXT", "MANUAL",
                                                   "policy-1", (0.1, 0.1, 0.2, 0.2))
            batch = approvals.approval_batch(chapter, run, versions[0])
            with self.assertRaises(psycopg.Error):
                with conn.transaction():
                    conn.execute(
                        "INSERT INTO fominha.approval_subjects"
                        "(approval_subject_id,approval_batch_id,occurrence_revision_id) VALUES(%s,%s,%s)",
                        (uuid4(), batch, revision))

    def test_direct_sql_cannot_change_closed_import_snapshot(self):
        with psycopg.connect(self.dsn) as conn:
            legacy = LegacyImportRepository(conn)
            batch = legacy.begin(str(uuid4()), "a" * 64, "sql-boundary")
            item = legacy.record(batch, "first.json", "CHECK", "LEGACY_UNVERIFIED")
            legacy.finish(batch, "COMPLETED")
            statements = (
                ("INSERT INTO fominha.legacy_import_items"
                 "(import_item_id,import_batch_id,legacy_path,contract_code,classification) "
                 "VALUES(%s,%s,'late.json','CHECK','LEGACY_UNVERIFIED')", (uuid4(), batch)),
                ("UPDATE fominha.legacy_import_items SET legacy_path='changed.json' "
                 "WHERE import_item_id=%s", (item,)),
                ("DELETE FROM fominha.legacy_import_items WHERE import_item_id=%s", (item,)),
            )
            for statement, params in statements:
                with self.assertRaises(psycopg.Error):
                    with conn.transaction():
                        conn.execute(statement, params)


if __name__ == "__main__":
    unittest.main()
