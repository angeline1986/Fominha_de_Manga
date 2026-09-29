import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image

from central_v2.backend.orchestration.textoff_merged import level2_transparent
from central_v2.backend.orchestration.textoff_merged.level2_process import process


class FakeReader:
    def __init__(self, *args, **kwargs):
        pass

    def detect(self, crop, **kwargs):
        return ([[[25, 75, 35, 65]]], [[]])


class FakeLama:
    def __call__(self, source, mask):
        return Image.new("RGB", source.size, (245, 245, 245))


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
                "level1": {"algorithm": "textoff_level1_balloon_transparency_gate_v3"},
            }
            (level1_dir / "clean-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

            with patch.dict("sys.modules", {"easyocr": types.SimpleNamespace(Reader=FakeReader)}), \
                 patch("central_v2.backend.orchestration.textoff_merged.level2_process._lama_model",
                       return_value=(FakeLama(), "test-model", "cpu")):
                report = process(source_dir, level1_dir, output_dir, output_dir / "report.json")

            self.assertTrue(report["integrity_ok"])
            self.assertGreaterEqual(report["duration_seconds"], 0)
            self.assertEqual(report["pages_with_text"], 1)
            final = np.asarray(Image.open(output_dir / "page-001-004_clean.png").convert("RGB"))
            mask = np.asarray(Image.open(output_dir / "page-001-004_text_mask.png")) > 0
            changed = np.any(final != source, axis=2)
            self.assertGreater(mask.sum(), 0)
            self.assertTrue(np.any(mask[20:24, 20:24]))
            self.assertTrue(np.all(changed[mask]))
            self.assertFalse(np.any(changed & ~mask))
            self.assertFalse(np.any(mask & (labels != 1)))

    def test_missing_or_invalid_level1_manifest_fails_closed(self):
        with tempfile.TemporaryDirectory() as root:
            base = Path(root)
            source, level1 = base / "source", base / "level1"
            source.mkdir()
            level1.mkdir()
            with self.assertRaisesRegex(FileNotFoundError, "level1-balloon-report"):
                process(source, level1, base / "out", base / "out" / "report.json")


if __name__ == "__main__":
    unittest.main()
