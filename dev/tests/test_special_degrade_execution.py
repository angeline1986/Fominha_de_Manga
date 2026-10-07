"""Degradê execution contracts with synthetic artifacts and a mocked worker."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from central_v2.backend.orchestration.textoff_merged.auto_cleaner_check_manifest import (
    SCHEMA as CHECK_SCHEMA, manifest_path as check_path,
)
from central_v2.backend.orchestration.textoff_merged.special_treatments_manifest import (
    rebuild_special_treatments, manifest_path as special_path,
)
from central_v2.backend.orchestration.textoff_merged.special_degrade_input import selected_input
from central_v2.backend.orchestration.textoff_merged.special_degrade_execution import execute_degrade
from central_v2.backend.orchestration.textoff_merged.special_treatments_query import query_special_treatments
from central_v2.backend.orchestration.textoff_merged.stages import (
    CONSOLIDATED, LEVEL1, LEVEL2, stage_chapter,
)
from central_v2.backend.orchestration.textoff_special.artifacts import sha256


class DegradeExecutionTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name)
        self.manga = self.output / "comix" / "Example"
        (self.manga / "IMG" / "1").mkdir(parents=True)
        self.check = check_path(self.manga, "1")
        self.check.parent.mkdir(parents=True)
        rows = [self.row("degrade-a", "residuo_degrade", 10),
                self.row("degrade-b", "residuo_degrade", 40),
                self.row("smooth", "residuo_gradiente", 70)]
        self.check.write_text(json.dumps({"schema": CHECK_SCHEMA, "version": 1,
            "provider": "comix", "manga": "Example", "chapter": "1",
            "source_snapshot": {}, "approved_occurrences": rows}), encoding="utf-8")
        rebuild_special_treatments(self.manga, {"provider": "comix", "obra": "Example",
                                                "capitulo": "1"}, "1")
        self.special = special_path(self.manga, "1")

    def row(self, identity, kind, x):
        return {"id": identity, "page": "page.png", "tipo": kind,
                "box_normalized": {"left": .1, "top": .1, "width": .2, "height": .2},
                "box_pixels": {"x": x, "y": 20, "width": 20, "height": 20},
                "origin": "MANUAL", "origins": ["MANUAL"]}

    def select(self, stage=LEVEL2, *, missing=False, wrong_hash=False):
        image = stage_chapter(self.manga, stage, "1") / "clean/page_clean.png"
        image.parent.mkdir(parents=True, exist_ok=True)
        image.write_bytes(b"level-one" if stage == LEVEL1 else b"level-two")
        consolidated = stage_chapter(self.manga, CONSOLIDATED, "1") / "json/clean-manifest.json"
        consolidated.parent.mkdir(parents=True, exist_ok=True)
        rows = [] if missing else [{"source": "page.png", "selected_from": stage,
                                    "artifact": "clean/page_clean.png",
                                    "sha256": "invalid" if wrong_hash else sha256(image)}]
        consolidated.write_text(json.dumps({"selections": rows}), encoding="utf-8")
        return image, consolidated

    def test_input_tracks_l1_and_l2_without_fallback(self):
        for stage in (LEVEL1, LEVEL2):
            image, manifest = self.select(stage)
            with patch("central_v2.backend.orchestration.textoff_merged.special_degrade_input.consolidated_is_current", return_value=True):
                source = selected_input(self.manga, "1", "page.png")
            self.assertEqual(source["selected_from"], stage)
            self.assertEqual(source["sha256"], sha256(image))
            self.assertEqual(source["consolidated_manifest_sha256"], sha256(manifest))
            self.assertEqual(source["level"], "MERGED_NIVEL_I" if stage == LEVEL1 else "MERGED_NIVEL_II")
        self.select(LEVEL2, missing=True)
        with patch("central_v2.backend.orchestration.textoff_merged.special_degrade_input.consolidated_is_current", return_value=True):
            with self.assertRaisesRegex(ValueError, "Seleção Consolidada ausente"):
                selected_input(self.manga, "1", "page.png")
        self.select(LEVEL2, wrong_hash=True)
        with patch("central_v2.backend.orchestration.textoff_merged.special_degrade_input.consolidated_is_current", return_value=True):
            with self.assertRaisesRegex(ValueError, "indisponível"):
                selected_input(self.manga, "1", "page.png")

    def run_mocked(self, changed=7, fail=False, retry=False):
        image, consolidated = self.select()
        original_hashes = (sha256(image), sha256(consolidated), sha256(self.check))
        staging = self.output / "staging"
        result = staging / "run123" / "treatment/01_local_heal.png"
        result.parent.mkdir(parents=True, exist_ok=True)
        result.write_bytes(b"processed-image")
        calls = []
        def fake_preview(_manga, payload, *, approved_check_rois=False, on_progress=None):
            self.assertTrue(approved_check_rois)
            calls.append(payload)
            if on_progress:
                on_progress({"stage": "ocr", "percent": 37, "message": "processando OCR"})
            if fail:
                return {"execution_status": "failed", "error": "worker failed"}
            return {"execution_status": "succeeded", "run_id": "run123",
                    "approved_check_rois": True,
                    "source": {"sha256": payload["expected_sha256"]},
                    "treatment": {"algorithm": "textoff_special_roi_degrade_v2"},
                    "result_file": "treatment/01_local_heal.png",
                    "validation": {"result_sha256": sha256(result), "changed_pixels": changed}}
        with patch("central_v2.backend.orchestration.textoff_merged.special_degrade_input.consolidated_is_current", return_value=True), \
             patch("central_v2.backend.orchestration.textoff_merged.special_degrade_execution.preview", side_effect=fake_preview), \
             patch("central_v2.backend.orchestration.textoff_merged.special_degrade_output.STAGING_ROOT", staging):
            outcome = execute_degrade(self.manga, "comix", ["1"], lambda *_: None, retry=retry)
        self.assertEqual(len(calls), 1, outcome)
        self.assertEqual(len(calls[0]["selections"]), 2)
        self.assertEqual(calls[0]["level"], "MERGED_NIVEL_II")
        self.assertEqual((sha256(image), sha256(consolidated), sha256(self.check)), original_hashes)
        self.assertEqual(calls[0]["expected_sha256"], sha256(image))
        return outcome, json.loads(self.special.read_text(encoding="utf-8"))

    def test_worker_progress_is_mapped_to_job_progress(self):
        image, _ = self.select()
        progress = []
        with patch("central_v2.backend.orchestration.textoff_merged.special_degrade_input.consolidated_is_current", return_value=True), \
             patch("central_v2.backend.orchestration.textoff_merged.special_degrade_execution.preview",
                   side_effect=lambda *args, **kwargs: (
                       kwargs["on_progress"]({"stage": "ocr", "percent": 37,
                                              "message": "processando OCR"}) or {
                           "execution_status": "failed", "error": "stop after progress"})), \
             patch("central_v2.backend.orchestration.textoff_merged.special_degrade_output.STAGING_ROOT",
                   self.output / "staging"):
            execute_degrade(self.manga, "comix", ["1"], lambda chapter, event:
                            progress.append((chapter, event)))
        self.assertTrue(any(event.get("percent") == 37 and event.get("stage") == "ocr"
                            and "processando OCR" in event.get("message", "")
                            for _, event in progress))

    def test_two_rois_one_preview_and_atomic_persistent_output(self):
        outcome, special = self.run_mocked()
        self.assertEqual(outcome[0]["status"], "processed")
        self.assertEqual([row["status"] for row in special["treatments"]["degrade"]],
                         ["processed", "processed"])
        self.assertEqual(special["treatments"]["gradiente_suave"][0]["status"], "pending")
        stage = stage_chapter(self.manga, "PINCEL_DEGRADE", "1", read_legacy=False)
        manifest = json.loads((stage / "json/degrade-manifest.json").read_text(encoding="utf-8"))
        record = manifest["pages"]["page.png"]
        self.assertEqual(record["occurrence_ids"], ["degrade-a", "degrade-b"])
        self.assertEqual(len(record["rois"]), 2)
        self.assertEqual(record["selected_from"], LEVEL2)
        self.assertEqual(record["output"]["sha256"], sha256(stage / record["output"]["artifact"]))
        self.assertEqual(record["status"], "processed")
        with patch("central_v2.backend.orchestration.textoff_merged.special_degrade_execution.preview") as preview:
            repeated = execute_degrade(self.manga, "comix", ["1"], lambda *_: None)
        self.assertEqual(repeated[0]["status"], "failed")
        preview.assert_not_called()

    def test_no_change_and_failure_statuses(self):
        outcome, special = self.run_mocked(changed=0)
        self.assertEqual(outcome[0]["status"], "no_change")
        self.assertEqual({row["status"] for row in special["treatments"]["degrade"]}, {"no_change"})
        with patch("central_v2.backend.orchestration.textoff_merged.special_degrade_execution.preview") as preview:
            repeated = execute_degrade(self.manga, "comix", ["1"], lambda *_: None, retry=True)
        self.assertEqual(repeated[0]["status"], "failed")
        preview.assert_not_called()
        self.select()
        for row in special["treatments"]["degrade"]:
            row["status"] = "pending"
        self.special.write_text(json.dumps(special), encoding="utf-8")
        failed, special = self.run_mocked(fail=True)
        self.assertEqual(failed[0]["status"], "failed")
        self.assertEqual({row["status"] for row in special["treatments"]["degrade"]}, {"failed"})
        self.assertFalse((stage_chapter(self.manga, "PINCEL_DEGRADE", "1", read_legacy=False)
                          / "clean/invalid.png").exists())

    def test_promotion_failure_marks_failed_without_publishing_output(self):
        with patch("central_v2.backend.orchestration.textoff_merged.special_degrade_output.promote_stage",
                   side_effect=OSError("promotion failed")):
            outcome, special = self.run_mocked()
        self.assertEqual(outcome[0]["status"], "failed")
        self.assertEqual({row["status"] for row in special["treatments"]["degrade"]}, {"failed"})
        stage = stage_chapter(self.manga, "PINCEL_DEGRADE", "1", read_legacy=False)
        self.assertFalse(stage.exists())

    def test_modified_roi_is_rejected_before_worker(self):
        special = json.loads(self.special.read_text(encoding="utf-8"))
        special["treatments"]["degrade"][0]["box_pixels"]["x"] += 1
        self.special.write_text(json.dumps(special), encoding="utf-8")
        with patch("central_v2.backend.orchestration.textoff_merged.special_degrade_execution.preview") as preview:
            outcome = execute_degrade(self.manga, "comix", ["1"], lambda *_: None)
        self.assertEqual(outcome[0]["status"], "failed")
        preview.assert_not_called()

    def test_mixed_pending_and_failed_chapter_offers_retry(self):
        special = json.loads(self.special.read_text(encoding="utf-8"))
        special["treatments"]["degrade"][0]["status"] = "failed"
        self.special.write_text(json.dumps(special), encoding="utf-8")
        summary = query_special_treatments(self.manga, "comix", "degrade")
        self.assertEqual(summary["chapters"][0]["status"], "failed")

    def test_failed_retry_revalidates_and_can_process(self):
        failed, _ = self.run_mocked(fail=True)
        self.assertEqual(failed[0]["status"], "failed")
        with patch("central_v2.backend.orchestration.textoff_merged.special_degrade_execution.preview") as preview:
            blocked = execute_degrade(self.manga, "comix", ["1"], lambda *_: None)
        self.assertEqual(blocked[0]["status"], "failed")
        preview.assert_not_called()
        self.select(wrong_hash=True)
        with patch("central_v2.backend.orchestration.textoff_merged.special_degrade_input.consolidated_is_current", return_value=True), \
             patch("central_v2.backend.orchestration.textoff_merged.special_degrade_execution.preview") as preview:
            stale = execute_degrade(self.manga, "comix", ["1"], lambda *_: None, retry=True)
        self.assertEqual(stale[0]["status"], "failed")
        preview.assert_not_called()
        succeeded, special = self.run_mocked(retry=True)
        self.assertEqual(succeeded[0]["status"], "processed")
        self.assertEqual({row["status"] for row in special["treatments"]["degrade"]}, {"processed"})
        with patch("central_v2.backend.orchestration.textoff_merged.special_degrade_execution.preview") as preview:
            repeated = execute_degrade(self.manga, "comix", ["1"], lambda *_: None, retry=True)
        self.assertEqual(repeated[0]["status"], "failed")
        preview.assert_not_called()


if __name__ == "__main__":
    unittest.main()
