import json
from types import SimpleNamespace
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np

from central_v2.backend.orchestration.textoff_merged import level1_cleaner
from central_v2.backend.orchestration.textoff_merged.transparency_artifacts import (
    LEVEL1_ARTIFACT_ALGORITHM, _bind_mask_labels, _transparent_balloon_masks,
)


class MergedLevel1AdapterTests(unittest.TestCase):
    def test_level1_uses_cleaner_and_promotes_transparency_artifacts_without_legacy_level2(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "page-001-005.png"
            source.write_bytes(b"source")
            target = root / "MERGED_NIVEL_I" / "1"

            def fake_cleaner(images, work, *_args):
                input_dir, output_dir = work / "input", work / "output"
                input_dir.mkdir()
                output_dir.mkdir()
                clean = output_dir / "page-001-005_clean.png"
                mask = output_dir / "page-001-005_mask.png"
                clean.write_bytes(b"clean")
                mask.write_bytes(b"mask")
                return input_dir, output_dir, [clean], [mask]

            report = {
                "algorithm": LEVEL1_ARTIFACT_ALGORITHM, "policy": "preserve-transparent",
                "fail_closed": True, "model": {"task": "segment"}, "pages_total": 1,
                "cleaner_mask_pixels": 100, "authorized_mask_pixels": 40,
                "authorized_percent": 40, "pages": [{
                    "source": source.name, "transparent_balloons": [{"balloon": 1}],
                    "transparent_components_deferred": 1,
                    "component_decisions": [{"component": 1, "reason": "transparent_balloon_deferred"}],
                }],
            }

            def fake_authorization(_images, output_dir, _raw, report_path, *_args, **_kwargs):
                page = report["pages"][0]
                page["transparent_balloons"][0]["mask_label"] = 1
                page["transparent_mask_artifact"] = "mask/page-001-005_transparent_balloons.png"
                page["deferred_text_mask_artifact"] = "mask/page-001-005_deferred_text.png"
                page["deferred_text_mask_pixels"] = 25
                (output_dir / Path(page["transparent_mask_artifact"]).name).write_bytes(b"labels")
                (output_dir / Path(page["deferred_text_mask_artifact"]).name).write_bytes(b"deferred")
                report_path.write_text(json.dumps(report), encoding="utf-8")
                return report

            with patch.object(level1_cleaner, "run_panel_cleaner", side_effect=fake_cleaner), \
                 patch.object(level1_cleaner, "run_balloon_authorization", side_effect=fake_authorization):
                result = level1_cleaner.clean_level1_chapter(
                    [source], target, source_stage="MERGE", progress_job=None, chapter_name="1",
                )

            manifest = json.loads((target / "json" / "clean-manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(result["level2_pending_pages"], [source.name])
            self.assertEqual(manifest["level2"]["status"], "not_run")
            self.assertEqual(manifest["level1"]["transparent_balloons_total"], 1)
            self.assertEqual(manifest["level1"]["transparent_mask_artifacts"], [
                "mask/page-001-005_transparent_balloons.png",
            ])
            self.assertEqual(manifest["level1"]["deferred_text_mask_artifacts"], [
                "mask/page-001-005_deferred_text.png",
            ])
            self.assertGreaterEqual(manifest["execution"]["duration_seconds"], 0)
            self.assertEqual(manifest["execution"]["duration_scope"],
                             "chapter_total_including_validation_and_promotion")
            self.assertTrue((target / "mask" / "page-001-005_transparent_balloons.png").is_file())
            self.assertTrue((target / "mask" / "page-001-005_deferred_text.png").is_file())
            self.assertTrue((target / "clean" / "page-001-005_clean.png").is_file())

    def test_each_transparent_detection_gets_its_mask_label(self):
        polygons = [np.array([[5, 5], [30, 5], [30, 30], [5, 30]]),
                    np.array([[35, 35], [60, 35], [60, 60], [35, 60]]),
                    np.array([[65, 65], [95, 65], [95, 95], [65, 95]])]
        prediction = SimpleNamespace(masks=SimpleNamespace(xy=polygons))
        image = np.full((100, 100, 3), 255, dtype=np.uint8)
        with patch("central_v2.backend.orchestration.textoff_merged.transparency_artifacts.policy.measure_transparency",
                   side_effect=[{"transparent": True}, {"transparent": False}, {"transparent": True}]):
            _labels, _combined, mapping = _transparent_balloon_masks(image, prediction, cv2, np)
        mapping[1]["bbox"] = [5, 5, 26, 26]
        mapping[3]["bbox"] = [65, 65, 31, 31]
        balloons = [{"balloon": 1, "bbox": [5, 5, 26, 26]}, {"balloon": 3, "bbox": [65, 65, 31, 31]}]
        _bind_mask_labels(balloons, mapping, "page.png")
        self.assertEqual([mapping[item]["mask_label"] for item in (1, 3)], [1, 2])
        self.assertEqual([item["mask_label"] for item in balloons], [1, 2])

    def test_missing_detection_to_mask_mapping_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, "Rótulo da máscara transparente ausente"):
            _bind_mask_labels([{"balloon": 2, "bbox": [1, 2, 3, 4]}], {}, "page.png")


if __name__ == "__main__":
    unittest.main()
