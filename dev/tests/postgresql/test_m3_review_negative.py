"""Negative, isolation and recovery checks for the opt-in M3 adapter."""

from __future__ import annotations

import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

import psycopg

from persistence.postgresql.artifact_store import ArtifactConflict, ArtifactStore
from persistence.postgresql.artifacts import ArtifactRepository
from persistence.postgresql.catalog import CatalogRepository
from persistence.postgresql.publications import PublicationRepository
from persistence.postgresql.runs import RunRepository


class M3NegativeReview(unittest.TestCase):
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
        cls.temp = TemporaryDirectory(prefix="fominha-m3-negative-")
        cls.store = ArtifactStore(Path(cls.temp.name) / "objects")

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def _page(self, conn, name):
        catalog, runs = CatalogRepository(conn), RunRepository(conn)
        artifacts = ArtifactRepository(conn, self.store)
        provider = catalog.provider("review-synthetic", "Review fixture")
        work = catalog.work(provider, str(uuid4()), name)
        chapter = catalog.chapter(work, "01")
        page = catalog.source_page(chapter, "page-01.png", "page-01.png")
        stage = catalog.stage("REVIEW_FIXTURE", "1", "Review fixture")
        run = runs.create(stage, str(uuid4()), "fingerprint", "PAGE")
        runs.add_scope(run, chapter, source_page_id=page)
        runs.transition(run, "CREATED", "RUNNING")
        runs.transition(run, "RUNNING", "SUCCEEDED")
        slot = artifacts.create_slot(chapter, "SOURCE_PAGE", stage, "SOURCE", source_page_id=page)
        version, receipt = artifacts.create_version(slot, data=f"image:{name}".encode(), run_id=run)
        artifacts.add_run_artifact(run, 0, version, "OUTPUT", "SOURCE")
        artifacts.set_state(version, "VALID")
        return chapter, page, run, slot, version, receipt

    def test_cross_chapter_page_scope_is_rejected(self):
        with psycopg.connect(self.dsn) as conn:
            _, page_a, _, _, _, _ = self._page(conn, "scope-a")
            chapter_b, _, run_b, _, _, _ = self._page(conn, "scope-b")
            with conn.transaction():
                with self.assertRaises(psycopg.Error):
                    RunRepository(conn).add_scope(run_b, chapter_b, ordinal=1, source_page_id=page_a)

    def test_same_chapter_wrong_page_output_is_rejected(self):
        with psycopg.connect(self.dsn) as conn:
            catalog, runs = CatalogRepository(conn), RunRepository(conn)
            artifacts = ArtifactRepository(conn, self.store)
            chapter, page_a, run_a, _, _, _ = self._page(conn, "same-chapter-pages")
            page_b = catalog.source_page(chapter, "page-02.png", "page-02.png")
            stage = conn.execute("SELECT stage_id FROM fominha.stage_runs WHERE stage_run_id=%s",
                                 (run_a,)).fetchone()[0]
            slot_b = artifacts.create_slot(chapter, "SOURCE_PAGE", stage, "OTHER_PAGE", source_page_id=page_b)
            version_b, _ = artifacts.create_version(slot_b, data=b"page b", run_id=run_a)
            with conn.transaction():
                with self.assertRaises(psycopg.Error):
                    artifacts.add_run_artifact(run_a, 0, version_b, "OUTPUT", "OTHER_PAGE")

    def test_create_only_and_corrupt_hash_target(self):
        with TemporaryDirectory(prefix="fominha-m3-corrupt-") as root:
            store = ArtifactStore(root)
            body = b"expected immutable bytes"
            digest = __import__("hashlib").sha256(body).hexdigest()
            path = store.path_for(digest)
            path.parent.mkdir(parents=True)
            path.write_bytes(b"different bytes")
            with self.assertRaises(ArtifactConflict):
                store.put_bytes(body)
            self.assertEqual(path.read_bytes(), b"different bytes")
            self.assertEqual(len(list(store.quarantine.glob("*.json"))), 1)

    def test_concurrent_same_blob_is_create_only(self):
        payload = b"concurrent synthetic object"
        with ThreadPoolExecutor(max_workers=8) as pool:
            receipts = list(pool.map(lambda _: self.store.put_bytes(payload), range(24)))
        self.assertEqual(len({item.storage_key for item in receipts}), 1)
        self.assertEqual(self.store.verify(receipts[0].storage_key).sha256, receipts[0].sha256)

    def test_failed_reset_publication_is_atomic(self):
        with psycopg.connect(self.dsn) as conn:
            chapter, _, run, slot, version, _ = self._page(conn, "reset-failure")
            artifacts = ArtifactRepository(conn, self.store)
            artifacts.add_run_artifact(run, 0, version, "INPUT", "RESET_TARGET")
            pub_id = None
            with self.assertRaises(ValueError):
                pub_id, _ = PublicationRepository(conn, self.store).publish(
                    chapter, run, [{"slot_id": slot, "version_id": version, "expected_revision": 0}],
                    str(uuid4()), "f" * 64, reset={"reason": "should rollback"})
            self.assertIsNone(conn.execute("SELECT 1 FROM fominha.active_artifacts WHERE artifact_slot_id=%s",
                                           (slot,)).fetchone())
            if pub_id is not None:
                self.assertEqual(conn.execute("SELECT count(*) FROM fominha.publications WHERE publication_id=%s",
                                              (pub_id,)).fetchone()[0], 0)
                self.assertEqual(conn.execute("SELECT count(*) FROM fominha.reset_events WHERE publication_id=%s",
                                              (pub_id,)).fetchone()[0], 0)

    def test_concurrent_publications_keep_one_active_revision(self):
        with psycopg.connect(self.dsn) as conn:
            chapter, page, run_a, slot, version_a, _ = self._page(conn, "publication-race")
            runs, artifacts = RunRepository(conn), ArtifactRepository(conn, self.store)
            stage = conn.execute("SELECT stage_id FROM fominha.artifact_slots WHERE artifact_slot_id=%s",
                                 (slot,)).fetchone()[0]
            run_b = runs.create(stage, str(uuid4()), "race-b", "PAGE")
            runs.add_scope(run_b, chapter, source_page_id=page)
            runs.transition(run_b, "CREATED", "RUNNING")
            runs.transition(run_b, "RUNNING", "SUCCEEDED")
            version_b, _ = artifacts.create_version(slot, data=b"race image b", run_id=run_b)
            artifacts.add_run_artifact(run_b, 0, version_b, "OUTPUT", "SOURCE")
            artifacts.set_state(version_b, "VALID")

        def publish(run_id, version_id):
            try:
                with psycopg.connect(self.dsn) as conn:
                    return PublicationRepository(conn, self.store).publish(
                        chapter, run_id, [{"slot_id": slot, "version_id": version_id,
                                           "expected_revision": 0}], str(uuid4()), "9" * 64)[1]
            except psycopg.Error as exc:
                return type(exc).__name__

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(lambda pair: publish(*pair),
                                     [(run_a, version_a), (run_b, version_b)]))
        self.assertEqual(outcomes.count("COMMITTED"), 1, outcomes)
        self.assertEqual(len(outcomes), 2)
        self.assertTrue(all(item in ("COMMITTED", "CONFLICT", "SerializationFailure") for item in outcomes),
                        outcomes)
        with psycopg.connect(self.dsn) as conn:
            active = conn.execute("SELECT artifact_version_id,revision FROM fominha.active_artifacts "
                                  "WHERE artifact_slot_id=%s", (slot,)).fetchone()
            self.assertIn(active[0], (version_a, version_b))
            self.assertEqual(active[1], 1)

    @unittest.expectedFailure
    def test_application_role_cannot_mark_unvalidated_blob_valid(self):
        from persistence.postgresql.artifacts import ArtifactRepository
        with psycopg.connect(self.dsn) as conn:
            _, _, run, slot, _, _ = self._page(conn, "validation-bypass")
            version, _ = ArtifactRepository(conn, self.store).create_version(
                slot, data=b"not validated", run_id=run)
            with self.assertRaises(psycopg.Error):
                with conn.transaction():
                    conn.execute("SET LOCAL ROLE fominha_app")
                    conn.execute("INSERT INTO fominha.artifact_state_events"
                                 "(state_event_id,artifact_version_id,sequence_no,state) "
                                 "VALUES(%s,%s,2,'VALID')", (uuid4(), version))

    @unittest.expectedFailure
    def test_approval_snapshot_must_match_chapter(self):
        from persistence.postgresql.approvals import ApprovalRepository
        with psycopg.connect(self.dsn) as conn:
            chapter_a, _, run_a, _, version_a, _ = self._page(conn, "approval-a")
            _, _, _, _, version_b, _ = self._page(conn, "approval-b")
            with self.assertRaises((ValueError, psycopg.Error)):
                ApprovalRepository(conn).approval_batch(chapter_a, run_a, version_b)

    @unittest.expectedFailure
    def test_decision_image_must_match_approved_page(self):
        from persistence.postgresql.approvals import ApprovalRepository
        with psycopg.connect(self.dsn) as conn:
            chapter_a, page_a, run_a, _, version_a, _ = self._page(conn, "decision-a")
            _, _, _, _, version_b, _ = self._page(conn, "decision-b")
            approvals = ApprovalRepository(conn)
            occurrence = approvals.occurrence(page_a, run_a)
            revision = approvals.revise_occurrence(occurrence, version_a, "TEXT", "MANUAL", "p1",
                                                   (0.1, 0.1, 0.2, 0.2))
            batch = approvals.approval_batch(chapter_a, run_a, version_a)
            subject = approvals.approval_subject(batch, revision)
            with self.assertRaises((ValueError, psycopg.Error)):
                approvals.decide(subject, "APPROVE", version_b, "p1", {})


if __name__ == "__main__":
    unittest.main()
