import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import cv2
import numpy as np

from central_v2.backend.orchestration.textoff_merged import level1_cleaner
from central_v2.backend.routes import textoff_merged as textoff_route


class Level1RawMaskDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.merge = self.root / "MERGE" / "1"
        self.merge.mkdir(parents=True)
        (self.merge / "merge-manifest.json").write_text('{"schema":"merge-test"}', encoding="utf-8")
        self.images = []
        for name in ("page-001-005.png", "page-005-009.png"):
            image = np.full((12, 16, 3), 255, dtype=np.uint8)
            path = self.merge / name
            self.assertTrue(cv2.imwrite(str(path), image))
            self.images.append(path)

    def _run(self, target, diagnostics=False):
        raw_bytes = {}

        def fake_cleaner(images, work, *_args):
            output = work / "output"
            output.mkdir()
            cleans, masks = [], []
            for index, image in enumerate(images):
                clean = output / f"{image.stem}_clean.png"
                mask = output / f"{image.stem}_mask.png"
                self.assertTrue(cv2.imwrite(str(clean), np.full((12, 16, 3), 230, dtype=np.uint8)))
                raw = np.zeros((12, 16), dtype=np.uint8)
                raw[2 + index:5 + index, 3:8] = 255
                self.assertTrue(cv2.imwrite(str(mask), raw))
                raw_bytes[image.name] = mask.read_bytes()
                cleans.append(clean)
                masks.append(mask)
            return work / "input", output, cleans, masks

        def fake_authorization(images, output_dir, raw_masks, report_path, *_args, **_kwargs):
            pages = []
            for image in images:
                authorized = np.zeros((12, 16), dtype=np.uint8)
                authorized[2:4, 3:6] = 255
                clean = np.full((12, 16, 3), 230, dtype=np.uint8)
                clean[authorized > 0] = 200
                self.assertTrue(cv2.imwrite(str(output_dir / f"{image.stem}_clean.png"), clean))
                self.assertTrue(cv2.imwrite(
                    str(output_dir / f"{image.stem}_mask.png"), authorized,
                ))
                self.assertTrue(cv2.imwrite(
                    str(output_dir / f"{image.stem}_transparent_balloons.png"),
                    np.zeros((12, 16), dtype=np.uint8),
                ))
                self.assertTrue(cv2.imwrite(
                    str(output_dir / f"{image.stem}_deferred_text.png"),
                    np.zeros((12, 16), dtype=np.uint8),
                ))
                pages.append({
                    "source": image.name,
                    "transparent_balloons": [],
                    "transparent_components_deferred": 0,
                    "transparent_mask_artifact": f"mask/{image.stem}_transparent_balloons.png",
                    "deferred_text_mask_artifact": f"mask/{image.stem}_deferred_text.png",
                    "deferred_text_mask_pixels": 0,
                    "component_decisions": [{"component": 1, "decision": "remove"}],
                })
            report = {
                "schema_version": 3,
                "algorithm": "test_authorization_v1",
                "policy": "test-policy",
                "fail_closed": True,
                "model": {"task": "test"},
                "pages_total": len(images),
                "cleaner_mask_pixels": 30,
                "authorized_mask_pixels": 12,
                "authorized_percent": 40.0,
                "pages": pages,
            }
            report_path.write_text(json.dumps(report), encoding="utf-8")
            return report

        with patch.object(level1_cleaner, "run_panel_cleaner", side_effect=fake_cleaner), \
             patch.object(level1_cleaner, "run_balloon_authorization", side_effect=fake_authorization):
            level1_cleaner.clean_level1_chapter(
                self.images, target, source_stage="MERGE", progress_job=None,
                chapter_name="1", diagnostics=diagnostics,
                provider="comix", manga_name="Gazing at you",
            )
        return raw_bytes

    def test_diagnostics_default_off_and_on_is_operationally_equivalent(self):
        off, on = self.root / "off", self.root / "on"
        self._run(off)
        produced = self._run(on, diagnostics=True)

        self.assertFalse((off / "diagnostics").exists())
        self.assertEqual(list(self.root.glob(".off.textoff-v2-*")), [])
        self.assertEqual(list(self.root.glob(".on.textoff-v2-*")), [])
        diagnostic_manifest = json.loads(
            (on / "diagnostics" / "diagnostics-manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(diagnostic_manifest["schema"], "textoff_level1_diagnostics_v1")
        self.assertEqual(diagnostic_manifest["provider"], "comix")
        self.assertEqual(diagnostic_manifest["manga"], "Gazing at you")
        self.assertEqual(diagnostic_manifest["chapter"], "1")
        self.assertEqual(diagnostic_manifest["source"]["stage"], "MERGE")
        self.assertTrue(diagnostic_manifest["execution_id"])
        self.assertTrue(diagnostic_manifest["diagnostics"]["raw_mask"]["enabled"])
        self.assertEqual(diagnostic_manifest["source"]["manifest_sha256"], hashlib.sha256(
            (self.merge / "merge-manifest.json").read_bytes()
        ).hexdigest())
        self.assertEqual(diagnostic_manifest["level1"]["official_manifest_sha256"], hashlib.sha256(
            (on / "json" / "clean-manifest.json").read_bytes()
        ).hexdigest())

        for image in self.images:
            entry = diagnostic_manifest["diagnostics"]["raw_mask"]["pages"][image.name]
            stored = on / "diagnostics" / entry["file"]
            self.assertTrue(entry["available"])
            self.assertEqual(stored.read_bytes(), produced[image.name])
            self.assertEqual(entry["sha256"], hashlib.sha256(produced[image.name]).hexdigest())
            self.assertEqual((entry["width"], entry["height"]), (16, 12))
            self.assertEqual(entry["mask_pixels"], 15)
            self.assertTrue((on / "json" / "clean-manifest.json").is_file())

        operational_files = [
            "clean/page-001-005_clean.png", "clean/page-005-009_clean.png",
            "mask/page-001-005_mask.png", "mask/page-005-009_mask.png",
            "mask/page-001-005_transparent_balloons.png",
            "mask/page-005-009_transparent_balloons.png",
            "mask/page-001-005_deferred_text.png", "mask/page-005-009_deferred_text.png",
            "json/level1-balloon-report.json", "json/level2-report.json",
        ]
        for relative in operational_files:
            self.assertEqual((off / relative).read_bytes(), (on / relative).read_bytes(), relative)
        off_manifest = json.loads((off / "json" / "clean-manifest.json").read_text())
        on_manifest = json.loads((on / "json" / "clean-manifest.json").read_text())
        off_manifest.pop("execution", None)
        on_manifest.pop("execution", None)
        self.assertEqual(off_manifest, on_manifest)

    def test_diagnostic_copy_failure_is_reported_without_invalidating_operational_run(self):
        target = self.root / "copy-failure"
        original_copy2 = shutil.copy2

        def fail_diagnostic_copy(source, destination, *args, **kwargs):
            if "raw_mask" in Path(destination).parts:
                raise PermissionError("diagnostic destination unavailable")
            return original_copy2(source, destination, *args, **kwargs)

        with patch.object(level1_cleaner.shutil, "copy2", side_effect=fail_diagnostic_copy), \
             patch.object(level1_cleaner, "run_panel_cleaner") as run_cleaner, \
             patch.object(level1_cleaner, "run_balloon_authorization") as authorize:
            # The adapter fixtures are reused while the copy failure is injected only
            # for the diagnostic destination.
            raw_bytes = {}

            def fake_cleaner(images, work, *_args):
                output = work / "output"
                output.mkdir()
                cleans, masks = [], []
                for image in images:
                    clean = output / f"{image.stem}_clean.png"
                    mask = output / f"{image.stem}_mask.png"
                    cv2.imwrite(str(clean), np.full((12, 16, 3), 230, dtype=np.uint8))
                    cv2.imwrite(str(mask), np.full((12, 16), 255, dtype=np.uint8))
                    raw_bytes[image.name] = mask.read_bytes()
                    cleans.append(clean); masks.append(mask)
                return work / "input", output, cleans, masks

            def fake_auth(images, output_dir, raw_masks, report_path, *_args, **_kwargs):
                pages=[]
                for image in images:
                    cv2.imwrite(str(output_dir / f"{image.stem}_clean.png"), np.full((12,16,3), 200, dtype=np.uint8))
                    cv2.imwrite(str(output_dir / f"{image.stem}_mask.png"), np.zeros((12,16), dtype=np.uint8))
                    cv2.imwrite(str(output_dir / f"{image.stem}_transparent_balloons.png"), np.zeros((12,16), dtype=np.uint8))
                    pages.append({"source":image.name,"transparent_balloons":[],"transparent_components_deferred":0,
                                  "transparent_mask_artifact":f"mask/{image.stem}_transparent_balloons.png",
                                  "deferred_text_mask_artifact":None})
                report={"pages_total":len(images),"algorithm":"test","pages":pages}
                report_path.write_text(json.dumps(report),encoding="utf-8")
                return report

            run_cleaner.side_effect = fake_cleaner
            authorize.side_effect = fake_auth
            level1_cleaner.clean_level1_chapter(
                self.images, target, source_stage="MERGE", progress_job=None,
                chapter_name="1", diagnostics=True, provider="comix", manga_name="Gazing at you",
            )

        manifest = json.loads((target / "diagnostics" / "diagnostics-manifest.json").read_text())
        for image in self.images:
            page = manifest["diagnostics"]["raw_mask"]["pages"][image.name]
            self.assertFalse(page["available"])
            self.assertIn("diagnostic destination unavailable", page["error"])
            self.assertNotIn("file", page)
            self.assertFalse((target / "diagnostics" / "raw_mask" / f"{image.stem}_raw_mask.png").exists())
        self.assertTrue((target / "clean" / "page-001-005_clean.png").is_file())
        self.assertTrue((target / "json" / "clean-manifest.json").is_file())
        self.assertTrue(run_cleaner.called)
        self.assertTrue(authorize.called)
        self.assertEqual(list(self.root.glob(".copy-failure.textoff-v2-*")), [])

    def test_route_diagnostics_is_strictly_opt_in(self):
        for requested, expected in ((True, True), (False, False), ("true", False), (None, False)):
            received = {}

            def fake_runner(_manga, _chapters, _progress, **kwargs):
                received.update(kwargs)
                return []

            def run_submitted(operation, **_kwargs):
                operation(lambda *_args: None, "job-test")
                return {"id": "job-test"}

            with patch.object(textoff_route, "_context", return_value=("comix", "Gazing at you")), \
                 patch.object(textoff_route, "resolve_manga", return_value=self.root), \
                 patch.object(textoff_route, "validate_selection", return_value=["1"]), \
                 patch.object(textoff_route, "legacy_server_active", return_value=False), \
                 patch.object(textoff_route, "execute_merged_level1", side_effect=fake_runner), \
                 patch.object(textoff_route, "submit", side_effect=run_submitted):
                response = textoff_route.execute_textoff_merged_level1_response(
                    {"provider": "comix", "manga": "Gazing at you", "chapters": ["1"],
                     "diagnostics": requested}, self.root,
                )
            self.assertEqual(response.status, 202)
            self.assertEqual(received["diagnostics"], expected)
            self.assertEqual(received["provider"], "comix")
            self.assertEqual(received["manga_name"], "Gazing at you")


if __name__ == "__main__":
    unittest.main()
