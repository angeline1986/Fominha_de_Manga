"""Audit, idempotency and orphan-recovery checks with synthetic records."""

from __future__ import annotations

import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

import psycopg

from persistence.postgresql.artifact_store import ArtifactStore
from persistence.postgresql.artifacts import ArtifactRepository
from persistence.postgresql.audit import AuditRepository
from persistence.postgresql.catalog import CatalogRepository
from persistence.postgresql.recovery import reconcile_store
from persistence.postgresql.runs import RunRepository


class M3RecoveryReview(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dsn = os.environ.get("FOMINHA_PG_TEST_DSN", "")
        if not cls.dsn:
            raise unittest.SkipTest("set FOMINHA_PG_TEST_DSN to a disposable M3 database")
        with psycopg.connect(cls.dsn) as conn:
            if not conn.execute("SELECT current_database()").fetchone()[0].startswith("fominha_m3_test_"):
                raise RuntimeError("refusing to test outside fominha_m3_* databases")
            if conn.execute("SELECT count(*) FROM public.fominha_schema_migrations").fetchone()[0] != 7:
                raise RuntimeError("run the complete integration suite against a fresh database")
        cls.temp = TemporaryDirectory(prefix="fominha-m3-recovery-")
        cls.store = ArtifactStore(Path(cls.temp.name) / "objects")

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_run_idempotency_and_audit_history(self):
        with psycopg.connect(self.dsn) as conn:
            stage = CatalogRepository(conn).stage("RECOVERY_FIXTURE", "1", "Recovery fixture")
            runs = RunRepository(conn)
            key = str(uuid4())
            first = runs.create(stage, key, "same-fingerprint", "CHAPTER")
            self.assertEqual(runs.create(stage, key, "same-fingerprint", "CHAPTER"), first)
            with self.assertRaises(ValueError):
                runs.create(stage, key, "different-fingerprint", "CHAPTER")
            audit = AuditRepository(conn)
            event = audit.append("SYNTHETIC", first, "CREATED", {"source": "test"}, "tester")
            history = audit.history("SYNTHETIC", first)
            self.assertEqual(history[-1]["event_type"], "CREATED")
            self.assertEqual(history[-1]["payload"], {"source": "test"})
            self.assertTrue(event)

    def test_blob_write_before_database_failure_is_reported_as_orphan(self):
        with psycopg.connect(self.dsn) as conn:
            artifacts = ArtifactRepository(conn, self.store)
            content = b"synthetic blob with missing slot"
            with self.assertRaises(ValueError):
                artifacts.create_version(uuid4(), data=content)
            receipt = self.store.put_bytes(content)
            report = reconcile_store(conn, self.store)
            item = next(row for row in report if row.get("storage_key") == receipt.storage_key)
            self.assertEqual(item["status"], "ORPHAN_CANDIDATE")
            self.assertTrue(receipt.path.exists())

    def test_missing_registered_blob_is_reported_without_metadata_deletion(self):
        with psycopg.connect(self.dsn) as conn:
            receipt = self.store.put_bytes(b"synthetic registered blob")
            object_id = uuid4()
            conn.execute("INSERT INTO fominha.artifact_objects(object_id,sha256,byte_size,media_type,storage_key) "
                         "VALUES(%s,%s,%s,%s,%s)",
                         (object_id, receipt.sha256, receipt.byte_size, "image/png", receipt.storage_key))
            receipt.path.unlink()
            item = next(row for row in reconcile_store(conn, self.store)
                        if row.get("storage_key") == receipt.storage_key)
            self.assertEqual(item["status"], "MISSING_OR_CORRUPT")
            self.assertEqual(conn.execute("SELECT count(*) FROM fominha.artifact_objects WHERE object_id=%s",
                                          (object_id,)).fetchone()[0], 1)

    @unittest.expectedFailure
    def test_finished_legacy_batch_rejects_late_items(self):
        from persistence.postgresql.legacy import LegacyImportRepository
        with psycopg.connect(self.dsn) as conn:
            legacy = LegacyImportRepository(conn)
            batch = legacy.begin(f"synthetic-{uuid4()}", "a" * 64, "importer-test")
            legacy.finish(batch, "COMPLETED")
            with self.assertRaises((ValueError, psycopg.Error)):
                legacy.record(batch, "late.json", "CHECK", "LEGACY_UNVERIFIED")


if __name__ == "__main__":
    unittest.main()
