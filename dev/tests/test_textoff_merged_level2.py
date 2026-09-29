import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image

from central_v2.backend.orchestration.textoff_merged import level2_transparent
from central_v2.backend.orchestration.textoff_merged.level2_process import process


class FakeLama:
    def __call__(self, source, mask):
        return Image.new("RGB", source.size, (245, 245, 245))


class IdentityLama:
    def __call__(self, source, _mask):
        return source.copy()


class TextoffMergedLevel2Tests(unittest.TestCase):
    def test_batch_cli_does_not_require_single_chapter_arguments(self):
        with tempfile.TemporaryDirectory() as root:
            manifest = Path(root) / "jobs.json"
            manifest.write_text("[]", encoding="utf-8")
            with patch.object(sys, "argv", ["level2_transparent.py", "--batch-manifest", str(manifest)]), \
                 patch.object(level2_transparent, "process_batch", return_value=[]):
                self.assertEqual(level2_transparent.main(), 0)

    def test_inpainting_is_limited_to_detected_ink_inside_saved_transparent_region(self):
        with tempfile.TemporaryDirectory() as root:
            base = Path(root)
            source_dir, level1_dir, output_dir = base / "source", base / "level1", base / "level2"
            source_dir.mkdir()
            level1_dir.mkdir()
            source = np.full((100, 100, 3), 230, dtype=np.uint8)
            source[45:55, 46:54] = (20, 20, 20)
            Image.fromarray(source).save(source_dir / "page-001-004.png")
            Image.fromarray(source).save(level1_dir / "page-001-004_clean.png")
            labels = np.zeros((100, 100), dtype=np.uint16)
            labels[12:88, 12:88] = 1
            Image.fromarray(labels).save(level1_dir / "page-001-004_transparent_balloons.png")
            deferred = np.zeros((100, 100), dtype=np.uint8)
            deferred[20:24, 20:24] = 255
            Image.fromarray(deferred).save(level1_dir / "page-001-004_deferred_text.png")
            balloon_report = {
                "pages": [{"source": "page-001-004.png", "transparent_mask_artifact": "page-001-004_transparent_balloons.png",
                           "deferred_text_mask_artifact": "page-001-004_deferred_text.png",
                           "transparent_components_deferred": 1,
                           "transparent_balloons": [{"balloon": 1, "mask_label": 1, "bbox": [10, 10, 80, 80]}]}],
            }
            (level1_dir / "level1-balloon-report.json").write_text(json.dumps(balloon_report), encoding="utf-8")
            manifest = {
                "integrity_ok": True,
                "source_artifacts": ["page-001-004.png"],
                "clean_artifacts": ["page-001-004_clean.png"],
                "level1": {"algorithm": "textoff_level1_balloon_transparency_gate_v4"},
            }
            (level1_dir / "clean-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

            with patch("central_v2.backend.orchestration.textoff_merged.level2_process._lama_model",
                       return_value=(FakeLama(), "test-model", "cpu")):
                report = process(source_dir, level1_dir, output_dir, output_dir / "json" / "report.json")

            self.assertTrue(report["integrity_ok"])
            self.assertEqual(report["reference_recipe"], "textoff_special_roi_transparent_legacy_v1")
            self.assertEqual(report["outcome"], "visual_changes")
            self.assertGreaterEqual(report["duration_seconds"], 0)
            self.assertEqual(report["pages_with_text"], 1)
            final = np.asarray(Image.open(output_dir / "clean" / "page-001-004_clean.png").convert("RGB"))
            mask = np.asarray(Image.open(output_dir / "mask" / "page-001-004_text_mask.png")) > 0
            changed = np.any(final != source, axis=2)
            self.assertGreater(mask.sum(), 0)
            self.assertTrue(np.any(mask[20:24, 20:24]))
            self.assertTrue(np.all(changed[mask]))
            self.assertFalse(np.any(changed & ~mask))
            self.assertFalse(np.any(mask & (labels != 1)))

    def test_zero_visual_changes_are_recorded_as_review_outcome(self):
        with tempfile.TemporaryDirectory() as root:
            base = Path(root)
            source_dir, level1_dir, output_dir = base / "source", base / "level1", base / "level2"
            source_dir.mkdir()
            level1_dir.mkdir()
            image = np.full((40, 40, 3), 230, dtype=np.uint8)
            image[18:22, 18:22] = 20
            Image.fromarray(image).save(source_dir / "page-001-004.png")
            Image.fromarray(image).save(level1_dir / "page-001-004_clean.png")
            labels = np.zeros((40, 40), dtype=np.uint16)
            labels[5:35, 5:35] = 1
            Image.fromarray(labels).save(level1_dir / "labels.png")
            deferred = np.zeros((40, 40), dtype=np.uint8)
            deferred[18:22, 18:22] = 255
            Image.fromarray(deferred).save(level1_dir / "deferred.png")
            (level1_dir / "level1-balloon-report.json").write_text(json.dumps({"pages": [{
                "source": "page-001-004.png", "transparent_mask_artifact": "labels.png",
                "deferred_text_mask_artifact": "deferred.png", "transparent_components_deferred": 1,
                "transparent_balloons": [{"balloon": 1, "mask_label": 1}],
            }]}), encoding="utf-8")
            (level1_dir / "clean-manifest.json").write_text(json.dumps({
                "integrity_ok": True, "source_artifacts": ["page-001-004.png"],
                "clean_artifacts": ["page-001-004_clean.png"],
                "level1": {"algorithm": "textoff_level1_balloon_transparency_gate_v4"},
            }), encoding="utf-8")
            with patch("central_v2.backend.orchestration.textoff_merged.level2_process._lama_model",
                       return_value=(IdentityLama(), "test-model", "cpu")):
                report = process(source_dir, level1_dir, output_dir, output_dir / "json" / "report.json")
            self.assertEqual(report["outcome"], "no_visual_change")
            self.assertGreater(report["mask_pixels"], 0)
            self.assertEqual(report["changed_pixels"], 0)

    def test_missing_mask_label_fails_instead_of_reporting_empty_success(self):
        with tempfile.TemporaryDirectory() as root:
            base = Path(root)
            source_dir, level1_dir = base / "source", base / "level1"
            source_dir.mkdir()
            level1_dir.mkdir()
            image = np.full((20, 20, 3), 240, dtype=np.uint8)
            Image.fromarray(image).save(source_dir / "page-001-004.png")
            Image.fromarray(image).save(level1_dir / "page-001-004_clean.png")
            Image.fromarray(np.ones((20, 20), dtype=np.uint16)).save(
                level1_dir / "page-001-004_transparent_balloons.png")
            Image.fromarray(np.ones((20, 20), dtype=np.uint8)).save(level1_dir / "deferred.png")
            (level1_dir / "level1-balloon-report.json").write_text(json.dumps({"pages": [{
                "source": "page-001-004.png", "transparent_mask_artifact": "page-001-004_transparent_balloons.png",
                "deferred_text_mask_artifact": "deferred.png", "transparent_components_deferred": 1,
                "transparent_balloons": [{"balloon": 1}],
            }]}), encoding="utf-8")
            (level1_dir / "clean-manifest.json").write_text(json.dumps({
                "integrity_ok": True, "source_artifacts": ["page-001-004.png"],
                "clean_artifacts": ["page-001-004_clean.png"],
                "level1": {"algorithm": "textoff_level1_balloon_transparency_gate_v4"},
            }), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "sem mask_label"):
                process(source_dir, level1_dir, base / "out", base / "out" / "report.json")

    def test_missing_or_invalid_level1_manifest_fails_closed(self):
        with tempfile.TemporaryDirectory() as root:
            base = Path(root)
            source, level1 = base / "source", base / "level1"
            source.mkdir()
            level1.mkdir()
            with self.assertRaisesRegex(FileNotFoundError, "level1-balloon-report"):
                process(source, level1, base / "out", base / "out" / "json" / "report.json")


if __name__ == "__main__":
    unittest.main()
