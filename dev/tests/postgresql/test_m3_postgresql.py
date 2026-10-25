"""Synthetic PostgreSQL integration checks; never point at operational data."""

from __future__ import annotations

import os
import shutil
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo

from persistence.postgresql.approvals import ApprovalRepository
from persistence.postgresql.artifact_store import ArtifactStore
from persistence.postgresql.artifacts import ArtifactRepository
from persistence.postgresql.backup import build_manifest, verify_manifest
from persistence.postgresql.catalog import CatalogRepository
from persistence.postgresql.invalidation import process_pending
from persistence.postgresql.legacy import LegacyImportRepository
from persistence.postgresql.migrations import migrate_down, migrate_up
from persistence.postgresql.publications import PublicationConflict, PublicationRepository
from persistence.postgresql.resolver import ArtifactResolver, ResolutionError
from persistence.postgresql.runs import RunRepository


class M3PostgresIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dsn = os.environ.get("FOMINHA_PG_TEST_DSN", "")
        if not cls.dsn:
            raise unittest.SkipTest("set FOMINHA_PG_TEST_DSN to a disposable M3 database")
        with psycopg.connect(cls.dsn) as conn:
            name = conn.execute("SELECT current_database()").fetchone()[0]
            if not name.startswith("fominha_m3_test_"):
                raise RuntimeError("tests require a fresh disposable fominha_m3_test_* database")
            if conn.execute("SELECT to_regclass('public.fominha_schema_migrations')").fetchone()[0]:
                raise RuntimeError("use a new empty test database for each suite run")
            migrate_up(conn)
        cls.temp = TemporaryDirectory(prefix="fominha-m3-test-")
        cls.store = ArtifactStore(Path(cls.temp.name) / "objects")

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "temp"):
            cls.temp.cleanup()

    def _assert_database_restore(self, conn):
        conn.commit()  # Establish the synthetic snapshot at a committed boundary.
        restore_db = f"fominha_m3_restore_{uuid4().hex[:12]}"
        admin_dsn = make_conninfo(self.dsn, dbname="postgres")
        with TemporaryDirectory(prefix="fominha-m3-dump-") as root:
            dump = Path(root) / "synthetic.dump"
            subprocess.run(["pg_dump", "--format=custom", "--no-owner", "--file", str(dump),
                            "--dbname", self.dsn], check=True, capture_output=True, text=True)
            with psycopg.connect(admin_dsn, autocommit=True) as admin:
                admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(restore_db)))
            try:
                restore_dsn = make_conninfo(self.dsn, dbname=restore_db)
                subprocess.run(["pg_restore", "--exit-on-error", "--no-owner", "--dbname", restore_dsn,
                                str(dump)], check=True, capture_output=True, text=True)
                query = "SELECT (SELECT count(*) FROM fominha.active_artifacts), " \
                        "(SELECT count(*) FROM fominha.reset_events), " \
                        "(SELECT count(*) FROM fominha.approval_decisions), " \
                        "(SELECT count(*) FROM fominha.legacy_import_items)"
                with psycopg.connect(restore_dsn) as restored:
                    self.assertEqual(restored.execute(query).fetchone(), conn.execute(query).fetchone())
            finally:
                with psycopg.connect(admin_dsn, autocommit=True) as admin:
                    admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(restore_db)))

    def test_end_to_end_approval_reset_backup_and_immutability(self):
        with psycopg.connect(self.dsn) as conn:
            catalog, runs = CatalogRepository(conn), RunRepository(conn)
            artifacts, approvals = ArtifactRepository(conn, self.store), ApprovalRepository(conn)
            publisher = PublicationRepository(conn, self.store)
            provider = catalog.provider("synthetic", "Synthetic")
            work = catalog.work(provider, str(uuid4()), "Synthetic work")
            chapter = catalog.chapter(work, "chapter-1")
            page = catalog.source_page(chapter, "page-1", "page-1.png")
            source_stage = catalog.stage("SYNTHETIC_SOURCE", "1", "Synthetic source")
            derived_stage = catalog.stage("SYNTHETIC_DERIVED", "1", "Synthetic derived")
            source_slot = artifacts.create_slot(chapter, "SOURCE_PAGE", source_stage, "SOURCE", source_page_id=page)

            def successful_run(stage, key, scope_type="PAGE"):
                run = runs.create(stage, f"{uuid4()}-{key}", key, scope_type)
                runs.add_scope(run, chapter, source_page_id=page)
                runs.transition(run, "CREATED", "RUNNING")
                runs.transition(run, "RUNNING", "SUCCEEDED")
                return run

            run1 = successful_run(source_stage, "source-1")
            v1, _ = artifacts.create_version(source_slot, data=b"synthetic page v1", run_id=run1)
            artifacts.add_run_artifact(run1, 0, v1, "OUTPUT", "SOURCE")
            artifacts.set_state(v1, "VALID")
            first = publisher.publish(chapter, run1, [{"slot_id": source_slot, "version_id": v1,
                "expected_revision": 0}], "publish-1", "a" * 64)
            self.assertEqual(first[1], "COMMITTED")
            self.assertEqual(publisher.publish(chapter, run1, [{"slot_id": source_slot, "version_id": v1,
                "expected_revision": 0}], "publish-1", "a" * 64), first)
            with self.assertRaises(PublicationConflict):
                publisher.publish(chapter, run1, [{"slot_id": source_slot, "version_id": v1,
                    "expected_revision": 0}], "publish-1", "f" * 64)

            run2 = successful_run(source_stage, "source-2")
            v2, _ = artifacts.create_version(source_slot, data=b"synthetic page v2", run_id=run2)
            artifacts.add_run_artifact(run2, 0, v2, "OUTPUT", "SOURCE")
            artifacts.set_state(v2, "VALID")
            self.assertEqual(publisher.publish(chapter, run2, [{"slot_id": source_slot, "version_id": v2,
                "expected_revision": 1}], "publish-2", "b" * 64)[1], "COMMITTED")
            reset_run = successful_run(source_stage, "reset-1")
            artifacts.add_run_artifact(reset_run, 0, v1, "INPUT", "RESET_TARGET")
            reset_result = publisher.publish(chapter, reset_run, [{"slot_id": source_slot, "version_id": v1,
                "expected_revision": 2}], "reset-1", "c" * 64, reset={"reason": "synthetic reset"})
            self.assertEqual(reset_result[1], "COMMITTED")
            self.assertEqual(conn.execute("SELECT revision FROM fominha.active_artifacts WHERE artifact_slot_id=%s",
                                          (source_slot,)).fetchone()[0], 3)

            occ = approvals.occurrence(page, run1)
            process_pending(conn)
            rev = approvals.revise_occurrence(occ, v1, "TEXT", "MANUAL", "policy-1", (0.1, 0.1, 0.2, 0.2))
            batch = approvals.approval_batch(chapter, run1, v1)
            subject = approvals.approval_subject(batch, rev)
            decision, _ = approvals.decide(subject, "APPROVE", v1, "policy-1", {}, actor_id="tester")
            output_slot = artifacts.create_slot(chapter, "SOURCE_PAGE", derived_stage, "DERIVED", source_page_id=page)
            derived_run = successful_run(derived_stage, "derived-1")
            candidate, _ = artifacts.create_version(output_slot, data=b"synthetic derived output", run_id=derived_run)
            artifacts.add_run_artifact(derived_run, 0, candidate, "OUTPUT", "RESULT")
            artifacts.add_dependency(candidate, v1, "SOURCE_IMAGE")
            approvals.add_dependency(candidate, subject, decision)
            artifacts.set_state(candidate, "VALID")
            self.assertEqual(publisher.publish(chapter, derived_run, [{"slot_id": output_slot,
                "version_id": candidate, "expected_revision": 0}], "derived-publish", "d" * 64)[1], "COMMITTED")
            final_stage = catalog.stage("SYNTHETIC_FINAL", "1", "Synthetic final")
            final_slot = artifacts.create_slot(chapter, "SOURCE_PAGE", final_stage, "FINAL",
                                               source_page_id=page)
            final_run = successful_run(final_stage, "final-1")
            final_version, _ = artifacts.create_version(final_slot, data=b"synthetic final output",
                                                        run_id=final_run)
            artifacts.add_run_artifact(final_run, 0, final_version, "OUTPUT", "FINAL")
            artifacts.add_dependency(final_version, candidate, "DERIVED_INPUT")
            artifacts.set_state(final_version, "VALID")
            self.assertEqual(publisher.publish(chapter, final_run, [{"slot_id": final_slot,
                "version_id": final_version, "expected_revision": 0}], "final-publish", "e" * 64)[1], "COMMITTED")
            resolver = ArtifactResolver(conn, self.store)
            self.assertEqual(resolver.resolve_active(final_slot).artifact_version_id, final_version)
            approvals.decide(subject, "REVOKE", v1, "policy-1", {}, actor_id="tester", reason="synthetic")
            self.assertGreaterEqual(process_pending(conn)["staled"], 2)
            with self.assertRaises(ResolutionError):
                resolver.resolve_active(final_slot)
            manifest = build_manifest(conn, self.store)
            self.assertGreaterEqual(verify_manifest(manifest, self.store)["objects_verified"], 3)
            with TemporaryDirectory(prefix="fominha-m3-store-backup-") as backup_root:
                copy = Path(backup_root) / "objects"
                shutil.copytree(self.store.root, copy)
                copied_store = ArtifactStore(copy)
                self.assertEqual(verify_manifest(manifest, copied_store),
                                 verify_manifest(manifest, self.store))
            self.assertTrue(self.store.put_bytes(b"synthetic page v1").reused)
            legacy = LegacyImportRepository(conn)
            import_id = legacy.begin("synthetic-root", "e" * 64, "test-importer-1")
            legacy.record(import_id, "legacy/page.json", "CHECK", "LEGACY_UNVERIFIED",
                          issue_code="SOURCE_AUTHORITY_UNKNOWN")
            legacy.finish(import_id, "PARTIAL")
            self._assert_database_restore(conn)

    def test_schema_and_append_only_guards(self):
        with psycopg.connect(self.dsn) as conn:
            self.assertEqual(conn.execute("SELECT count(*) FROM public.fominha_schema_migrations").fetchone()[0], 7)
            self.assertTrue(conn.execute("SELECT to_regclass('fominha.legacy_import_items')").fetchone()[0])
            with self.assertRaises(psycopg.Error):
                conn.execute("UPDATE fominha.artifact_objects SET byte_size=byte_size")


if __name__ == "__main__":
    unittest.main()
