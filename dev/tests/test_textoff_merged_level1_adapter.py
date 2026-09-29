import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from central_v2.backend.orchestration.textoff_merged import level1_cleaner


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
                "algorithm": "authorization-v3", "policy": "preserve-transparent",
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
                page["transparent_mask_artifact"] = "page-001-005_transparent_balloons.png"
                page["deferred_text_mask_artifact"] = "page-001-005_deferred_text.png"
                page["deferred_text_mask_pixels"] = 25
                (output_dir / page["transparent_mask_artifact"]).write_bytes(b"labels")
                (output_dir / page["deferred_text_mask_artifact"]).write_bytes(b"deferred")
                report_path.write_text(json.dumps(report), encoding="utf-8")
                return report

            with patch.object(level1_cleaner, "run_panel_cleaner", side_effect=fake_cleaner), \
                 patch.object(level1_cleaner, "run_balloon_authorization", side_effect=fake_authorization):
                result = level1_cleaner.clean_level1_chapter(
                    [source], target, source_stage="MERGE", progress_job=None, chapter_name="1",
                )

            manifest = json.loads((target / "clean-manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(result["level2_pending_pages"], [source.name])
            self.assertEqual(manifest["level2"]["status"], "not_run")
            self.assertEqual(manifest["level1"]["transparent_balloons_total"], 1)
            self.assertEqual(manifest["level1"]["deferred_text_mask_artifacts"], [
                "page-001-005_deferred_text.png",
            ])
            self.assertGreaterEqual(manifest["execution"]["duration_seconds"], 0)
            self.assertEqual(manifest["execution"]["duration_scope"],
                             "chapter_total_including_validation_and_promotion")
            self.assertTrue((target / "page-001-005_transparent_balloons.png").is_file())
            self.assertTrue((target / "page-001-005_deferred_text.png").is_file())


if __name__ == "__main__":
    unittest.main()
