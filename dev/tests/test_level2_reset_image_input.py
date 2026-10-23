import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image

from central_v2.backend.orchestration.textoff_merged.level2_process import process


class WhiteInpainter:
    def __call__(self, source, _mask):
        return Image.new("RGB", source.size, (245, 245, 245))


class Level2ResetImageInputTests(unittest.TestCase):
    def test_reset_page_is_the_output_base_and_other_pages_keep_level1(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source_dir, level1_dir, output = root / "source", root / "level1", root / "out"
            source_dir.mkdir()
            level1_dir.mkdir()
            page = "page-001-004.png"
            reset_image = np.full((100, 100, 3), 80, dtype=np.uint8)
            level1_image = np.full((100, 100, 3), 220, dtype=np.uint8)
            Image.fromarray(reset_image).save(source_dir / page)
            Image.fromarray(level1_image).save(level1_dir / "page-001-004_clean.png")
            labels = np.zeros((100, 100), dtype=np.uint16)
            labels[10:90, 10:90] = 1
            Image.fromarray(labels).save(level1_dir / "labels.png")
            deferred = np.zeros((100, 100), dtype=np.uint8)
            deferred[20:80, 20:80] = 255
            Image.fromarray(deferred).save(level1_dir / "deferred.png")
            (level1_dir / "level1-balloon-report.json").write_text(json.dumps({"pages": [{
                "source": page, "transparent_mask_artifact": "labels.png",
                "deferred_text_mask_artifact": "deferred.png", "transparent_components_deferred": 1,
                "transparent_balloons": [{"balloon": 1, "mask_label": 1}],
            }]}), encoding="utf-8")
            (level1_dir / "clean-manifest.json").write_text(json.dumps({
                "integrity_ok": True, "source_artifacts": [page],
                "clean_artifacts": ["page-001-004_clean.png"],
                "level1": {"algorithm": "textoff_level1_balloon_transparency_gate_v4"},
            }), encoding="utf-8")
            reset_file = root / "reset_merge" / page
            reset_file.parent.mkdir()
            Image.fromarray(reset_image).save(reset_file)
            reset_hash = hashlib.sha256(reset_file.read_bytes()).hexdigest()
            authority = {"kind": "CHECK_RESET", "path": f"reset_merge/{page}",
                         "sha256": reset_hash, "reset_id": "reset-1", "source": "MERGE"}
            protections = {page: [{"id": "roi-1", "tipo": "outro", "box_normalized": {
                "left": 0.3, "top": 0.3, "width": 0.4, "height": 0.4}}]}
            with patch("central_v2.backend.orchestration.textoff_merged.level2_process._lama_model",
                       return_value=(WhiteInpainter(), "test-model", "cpu")):
                report = process(
                    source_dir, level1_dir, output, output / "json/report.json",
                    candidate_pages={page}, protected_occurrences=protections,
                    reset_bases={page: {"path": str(reset_file), "sha256": reset_hash,
                                        "source": authority}},
                )

            row = report["pages"][0]
            result = np.asarray(Image.open(output / "clean/page-001-004_clean.png"))
            roi = np.zeros((100, 100), dtype=bool)
            roi[30:70, 30:70] = True
            self.assertEqual(report["reset_base_contract"], "check_reset_v1")
            self.assertEqual(row["reset_base_source"], authority)
            self.assertEqual(row["protected_types_applied"], ["outro"])
            self.assertTrue(np.array_equal(result[roi], reset_image[roi]))
            self.assertTrue(np.array_equal(result[0, 0], reset_image[0, 0]))
            self.assertTrue(np.array_equal(result[25, 25], np.full(3, 245)))


if __name__ == "__main__":
    unittest.main()
