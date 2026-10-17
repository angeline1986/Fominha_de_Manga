"""Disposable publisher contract and rollback tests."""
from pathlib import Path
from tempfile import TemporaryDirectory
import hashlib
import json
import unittest
from unittest.mock import patch

from central_v2.backend.orchestration.combo_turbo.publication import (
    _blocked, _require_same_run,
)
from central_v2.backend.orchestration.textoff_merged import special_styled_transaction as tx
from central_v2.backend.orchestration.combo_turbo.publication_candidates import _write_final
from central_v2.backend.orchestration.textoff_merged.final_consolidated import AUTOMATIC_ORIGINS
from central_v2.backend.orchestration.textoff_merged.stages import COMBO_TURBO, stage_chapter
from central_v2.backend.orchestration.textoff_merged.final_consolidated_manifest import read_manifest
from central_v2.backend.orchestration.combo_turbo import publication_manifest


class ComboPublicationTests(unittest.TestCase):
    def test_same_run_is_idempotent_only_for_identical_page_provenance(self):
        row = {"status": "COMPOSED", "sha256": "a" * 64,
               "report_sha256": "b" * 64, "check_manifest_sha256": "c" * 64,
               "level1_manifest_sha256": "d" * 64,
               "source_solids_sha256": None, "source_glass_sha256": "e" * 64,
               "mask_sha256": "f" * 64}
        _require_same_run({"page-001.png": row}, {"page-001.png": dict(row)})
        changed = {**row, "source_glass_sha256": "0" * 64}
        with self.assertRaisesRegex(ValueError, "proveniência divergente"):
            _require_same_run({"page-001.png": row}, {"page-001.png": changed})
        with self.assertRaisesRegex(ValueError, "conjunto de páginas"):
            _require_same_run({"page-001.png": row}, {})

    def test_blocked_statuses_are_counted_without_promoting_no_work(self):
        pages = {"a": {"status": "COMPOSED"}, "b": {"status": "NO_WORK"},
                 "c": {"status": "CONFLICT"}, "d": {"status": "BLOCKED"},
                 "e": {"status": "FAILED"}}
        self.assertEqual(_blocked(pages), 3)

    def test_no_work_and_conflict_create_manifest_rows_without_images(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            manga = root / "comix" / "work"
            manga.mkdir(parents=True)
            staged = root / "combo-stage"
            pages = {"page-001.png": {"page": "page-001.png", "status": "NO_WORK"},
                     "page-002.png": {"page": "page-002.png", "status": "CONFLICT",
                                      "reasons": ["OVERLAP"]}}
            with patch.object(publication_manifest, "_source_refs", return_value={}):
                payload, _ = publication_manifest.prepare_generation(
                    manga, "12", staged, pages, run_id="test-run")
            self.assertEqual(payload["pages"]["page-001.png"]["status"], "NO_WORK")
            self.assertEqual(payload["pages"]["page-002.png"]["status"], "CONFLICT")
            self.assertFalse(list((staged / "generations").rglob("*.png")))

    def test_failure_after_final_swap_restores_all_previous_directories(self):
        with TemporaryDirectory() as temporary:
            manga = Path(temporary) / "manga"
            manga.mkdir()
            _identity, folder = tx.begin(manga, "12")
            entries = []
            for name in ("combo", "logical", "final"):
                target = manga / name
                target.mkdir()
                (target / "revision").write_text("old")
                staged = folder / f"staged-{name}"
                staged.mkdir()
                (staged / "revision").write_text("new")
                entries.append({"target": str(target), "staged": str(staged)})

            def reject_published_state():
                self.assertEqual((manga / "final/revision").read_text(), "new")
                raise ValueError("simulated post-promotion validation failure")

            with self.assertRaisesRegex(ValueError, "post-promotion"):
                tx.publish(manga, folder, entries, lambda: None,
                           validate_published=reject_published_state)
            for name in ("combo", "logical", "final"):
                self.assertEqual((manga / name / "revision").read_text(), "old")
            self.assertFalse(folder.exists())

    def test_changed_final_image_is_archived_and_readable(self):
        with TemporaryDirectory() as temporary:
            manga = Path(temporary) / "comix" / "work"
            combo = manga / "combo-candidate"
            logical = manga / "logical-candidate"
            final = stage_chapter(manga, "CONSOLIDADO_FINAL", "12", read_legacy=False)
            combo.mkdir(parents=True)
            logical.mkdir()
            final.mkdir(parents=True)
            (combo / "clean").mkdir()
            old, new = b"previous-final", b"combo-final"
            (final / "page-001.png").write_bytes(old)
            (combo / "clean/page-001_combo.png").write_bytes(new)
            manifest = logical / "json/clean-manifest.json"
            manifest.parent.mkdir()
            manifest.write_text("{}\n")
            digest = lambda value: hashlib.sha256(value).hexdigest()
            prior = {"pages": {"page-001.png": {"page": "page-001.png",
                "artifact": "page-001.png", "sha256": digest(old),
                "origin": "AUTO_CLEANER"}}, "history": []}
            selections = [{"source": "page-001.png", "selected_from": COMBO_TURBO,
                "artifact": "clean/page-001_clean.png",
                "source_artifact": "clean/page-001_combo.png", "sha256": digest(new)}]
            _write_final(manga, "12", combo, logical, {"selections": selections},
                         final.with_name("candidate-final"), prior)
            candidate = final.with_name("candidate-final")
            payload = read_manifest(candidate / "json/final-manifest.json", manga, "12")
            record = payload["history"][0]
            archive = candidate / record["archived_artifact"]
            self.assertEqual(archive.read_bytes(), old)
            self.assertEqual(record["archived_sha256"], digest(old))
            self.assertEqual((candidate / "page-001.png").read_bytes(), new)


if __name__ == "__main__":
    unittest.main()
