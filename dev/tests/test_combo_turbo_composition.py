import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image

from central_v2.backend.orchestration.combo_turbo.composition import compose_page
from central_v2.backend.orchestration.textoff_special.artifacts import sha256
from central_v2.backend.orchestration.textoff_merged.auto_cleaner_check_manifest import manifest_path
from central_v2.backend.orchestration.textoff_merged.stages import LEVEL1, stage_chapter


class CompositionFixture(unittest.TestCase):
    page = "page-061-065.png"

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manga = self.root / "comix" / "Sample"
        self.manga.mkdir(parents=True)
        self.l1 = stage_chapter(self.manga, LEVEL1, "12", read_legacy=False) / "clean" / f"{Path(self.page).stem}_clean.png"
        self.l1.parent.mkdir(parents=True)
        self.level1 = np.full((5, 6, 3), 10, dtype=np.uint8)
        self.solids = self.level1.copy()
        self.solids[1:3, 1:3] = 20
        self.glass = self.level1.copy()
        self.glass[3:5, 3:6] = 30
        self.mask_array = np.zeros((5, 6), dtype=np.uint8)
        self.mask_array[3:5, 3:6] = 255
        self._save(self.l1, self.level1)
        input_dir = self.manga / "fixtures"
        input_dir.mkdir()
        self.solids_path = input_dir / "solids.png"
        self.glass_path = input_dir / "glass.png"
        self.mask_path = input_dir / "mask.png"
        self._save(self.solids_path, self.solids)
        self._save(self.glass_path, self.glass)
        self._save(self.mask_path, self.mask_array)
        self.output = self.root / "experimental"
        self.check = manifest_path(self.manga, "12")
        self.check.parent.mkdir(parents=True)
        self.check.write_text(json.dumps({"fixture": "current-check"}), encoding="utf-8")
        self.statuses = {}
        self.hash_overrides = {}

    @staticmethod
    def _save(path, array):
        Image.fromarray(array).save(path)

    def _validator(self, _manga, _provider, _chapter, _page, stage):
        status = self.statuses.get(stage, "REUSABLE")
        target = self.solids_path if stage == "SOLIDOS" else self.glass_path
        mask_hash = sha256(self.mask_path)
        return {"stage": stage, "chapter": "12", "page": self.page,
                "status": status, "integrity_ok": status == "REUSABLE",
                "check_verified": status == "REUSABLE",
                "artifact_sha256": self.hash_overrides.get(stage, sha256(target)),
                "mask_sha256": self.hash_overrides.get("MASK", mask_hash),
                "manifest_sha256": "a" * 64, "reasons": self.statuses.get(f"{stage}_reasons", [])}

    def compose(self, solids=True, glass=True, **kwargs):
        solid_path = kwargs.pop("solids_path", self.solids_path if solids else None)
        glass_file = kwargs.pop("glass_path", self.glass_path if glass else None)
        mask_file = kwargs.pop("mask_path", self.mask_path if glass else None)
        return compose_page(
            self.manga, "comix", "12", self.page, level1_path=self.l1,
            output_dir=self.output, solids_path=solid_path,
            glass_path=glass_file, mask_path=mask_file, **kwargs)

    def patched(self):
        return (patch("central_v2.backend.orchestration.combo_turbo.composition_inputs.validate_page",
                      side_effect=self._validator),
                patch("central_v2.backend.orchestration.combo_turbo.composition.validate_page",
                      side_effect=self._validator))

    def test_both_stages_compose_pixel_exactly_and_report_provenance(self):
        with self.patched()[0], self.patched()[1]:
            item = self.compose()
        self.assertEqual(item["status"], "COMPOSED")
        image = np.asarray(Image.open(item["result_path"]))
        expected = self.solids.copy()
        expected[self.mask_array > 0] = self.glass[self.mask_array > 0]
        np.testing.assert_array_equal(image, expected)
        self.assertEqual(item["overlap_pixels"], 0)
        self.assertEqual(item["result_sha256"], sha256(Path(item["result_path"])))
        for field in ("source_level1_sha256", "source_solids_sha256", "source_glass_sha256",
                      "mask_sha256", "check_manifest_sha256", "result_sha256"):
            self.assertTrue(item[field])

    def test_solid_only_returns_solid_pixels(self):
        with self.patched()[0], self.patched()[1]:
            item = self.compose(glass=False)
        np.testing.assert_array_equal(np.asarray(Image.open(item["result_path"])), self.solids)

    def test_glass_only_uses_effective_mask_over_level1(self):
        with self.patched()[0], self.patched()[1]:
            item = self.compose(solids=False)
        expected = self.level1.copy()
        expected[self.mask_array > 0] = self.glass[self.mask_array > 0]
        np.testing.assert_array_equal(np.asarray(Image.open(item["result_path"])), expected)

    def test_no_work_creates_no_output(self):
        item = self.compose(solids=False, glass=False)
        self.assertEqual(item["status"], "NO_WORK")
        self.assertFalse(self.output.exists())

    def test_stale_solid_and_unverified_glass_are_not_reused(self):
        self.statuses["SOLIDOS"] = "STALE"
        with self.patched()[0], self.patched()[1]:
            item = self.compose(glass=False)
        self.assertEqual(item["status"], "STALE")
        self.assertFalse(self.output.exists())
        self.statuses["GLASS"] = "UNVERIFIED"
        with self.patched()[0], self.patched()[1]:
            item = self.compose(solids=False)
        self.assertEqual(item["status"], "UNVERIFIED")
        self.assertFalse(self.output.exists())

    def test_absent_file_hash_mask_hash_and_dimensions_fail_closed(self):
        with self.patched()[0], self.patched()[1]:
            missing = self.compose(glass=False, solids_path=self.root / "absent.png")
        self.assertIn("INPUT_MISSING", missing["reasons"])
        self.hash_overrides["SOLIDOS"] = "0" * 64
        with self.patched()[0], self.patched()[1]:
            self.assertIn("SOLIDOS_HASH_MISMATCH", self.compose(glass=False)["reasons"])
        self.hash_overrides.clear()
        self.hash_overrides["MASK"] = "0" * 64
        with self.patched()[0], self.patched()[1]:
            self.assertIn("GLASS_MASK_HASH_MISMATCH", self.compose(solids=False)["reasons"])
        self.hash_overrides.clear()
        self._save(self.glass_path, np.zeros((4, 6, 3), dtype=np.uint8))
        with self.patched()[0], self.patched()[1]:
            self.assertIn("DIMENSION_MISMATCH", self.compose(solids=False)["reasons"])

    def test_empty_mask_preserves_base_and_non_candidate_means_no_work(self):
        self._save(self.mask_path, np.zeros((5, 6), dtype=np.uint8))
        with self.patched()[0], self.patched()[1]:
            item = self.compose()
        np.testing.assert_array_equal(np.asarray(Image.open(item["result_path"])), self.solids)
        self.output = self.root / "noncandidate"
        self.statuses["GLASS"] = "MISSING"
        self.statuses["GLASS_reasons"] = ["PAGE_NOT_GLASS_CANDIDATE"]
        with self.patched()[0], self.patched()[1]:
            item = self.compose(solids=False)
        self.assertEqual(item["status"], "NO_WORK")

    def test_inputs_unchanged_and_output_is_deterministic(self):
        paths = [self.l1, self.solids_path, self.glass_path, self.mask_path, self.check]
        before = {path: sha256(path) for path in paths}
        with self.patched()[0], self.patched()[1]:
            first = self.compose()
        self.output = self.root / "second"
        with self.patched()[0], self.patched()[1]:
            second = self.compose()
        self.assertEqual(first["result_sha256"], second["result_sha256"])
        self.assertEqual(before, {path: sha256(path) for path in paths})

    def test_write_failure_leaves_no_result_bundle(self):
        with self.patched()[0], self.patched()[1], patch("PIL.Image.Image.save", side_effect=OSError("disk")):
            item = self.compose()
        self.assertEqual(item["reasons"], ["WRITE_FAILED"])
        self.assertFalse((self.output / "12-page-061-065-combo").exists())

    def test_rejects_non_disposable_manga_root(self):
        item = compose_page(Path.cwd(), "comix", "12", self.page,
                            level1_path=self.l1, output_dir=self.output,
                            solids_path=self.solids_path)
        self.assertEqual(item["reasons"], ["DISPOSABLE_ROOT_REQUIRED"])
        self.assertFalse(self.output.exists())

    def test_one_pixel_overlap_blocks_and_reports_coordinate(self):
        self.solids[3, 3] = 20
        self._save(self.solids_path, self.solids)
        with self.patched()[0], self.patched()[1]:
            item = self.compose()
        self.assertEqual(item["status"], "CONFLICT")
        self.assertEqual(item["overlap_pixels"], 1)
        self.assertEqual(item["overlap_bounds"], {"x": 3, "y": 3, "width": 1, "height": 1})
        self.assertFalse(self.output.exists())

    def test_border_overlap_blocks_without_changing_mask(self):
        self.solids[4, 5] = 20
        self._save(self.solids_path, self.solids)
        mask_before = self.mask_path.read_bytes()
        with self.patched()[0], self.patched()[1]:
            item = self.compose()
        self.assertEqual(item["status"], "CONFLICT")
        self.assertEqual(item["overlap_bounds"]["x"] + item["overlap_bounds"]["width"], 6)
        self.assertEqual(self.mask_path.read_bytes(), mask_before)


if __name__ == "__main__":
    unittest.main()
