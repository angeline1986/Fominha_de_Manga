import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from central_v2.backend.orchestration.combo_turbo.solids_validator import validate_solids_page
from central_v2.backend.orchestration.textoff_special.artifacts import sha256
from central_v2.backend.orchestration.textoff_merged.auto_cleaner_check_manifest import (
    MANIFEST_NAME, SCHEMA, manifest_path,
)
from central_v2.backend.orchestration.textoff_merged.solid_stage import STAGE
from central_v2.backend.orchestration.textoff_merged.stages import LEVEL1, stage_chapter


class ComboSolidsValidationTests(unittest.TestCase):
    page = "page-061-065.png"

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.manga = Path(self.temp.name) / "comix" / "Sample"
        self.manga.mkdir(parents=True)
        self.source = stage_chapter(self.manga, LEVEL1, "12", read_legacy=False) / "clean" / "page-061-065_clean.png"
        self.source.parent.mkdir(parents=True)
        Image.new("RGB", (8, 9), "white").save(self.source)
        self.folder = stage_chapter(self.manga, STAGE, "12", read_legacy=False)
        (self.folder / "clean").mkdir(parents=True)
        (self.folder / "mask").mkdir()
        self.output = self.folder / "clean/page-061-065_clean.png"
        self.mask = self.folder / "mask/page-061-065_mask.png"
        Image.new("RGB", (8, 9), "black").save(self.output)
        Image.new("L", (8, 9), 0).save(self.mask)
        self.check = manifest_path(self.manga, "12")
        self.check.parent.mkdir(parents=True)
        self.write_check()
        self.write_solid_manifest()

    def write_check(self, ident="roi-1", extra=None):
        value = {"schema": SCHEMA, "version": 1, "provider": "comix",
                 "manga": "Sample", "chapter": "12", "source_snapshot": {},
                 "approved_occurrences": [{"id": ident, "page": self.page,
                                            "tipo": "residuo_balao_solido_branco"}]}
        value.update(extra or {})
        self.check.write_text(json.dumps(value), encoding="utf-8")

    def write_solid_manifest(self, ident="roi-1"):
        payload = {"schema": "textoff_solid_stage_v1", "provider": "comix",
                   "manga": "Sample", "chapter": "12", "preview_only": True,
                   "check_sha256": sha256(self.check),
                   "pages": [{"page": self.page, "source_sha256": sha256(self.source),
                              "result_sha256": sha256(self.output), "mask_sha256": sha256(self.mask)}],
                   "regions": [{"id": ident, "page": self.page}]}
        (self.folder / "solid-white-manifest.json").write_text(
            json.dumps(payload), encoding="utf-8")

    def validate(self):
        with patch("central_v2.backend.orchestration.combo_turbo.solids_validator.source_for",
                   return_value=self.source):
            return validate_solids_page(self.manga, "comix", "12", self.page)

    def test_valid_preview_is_reusable_without_promotion(self):
        item = self.validate()
        self.assertEqual(item["status"], "REUSABLE")
        self.assertTrue(item["integrity_ok"])
        self.assertTrue(item["check_verified"])
        self.assertTrue(item["preview_only"])

    def test_manga_identity_mismatch_is_invalid(self):
        payload = json.loads((self.folder / "solid-white-manifest.json").read_text())
        payload["manga"] = "different title"
        (self.folder / "solid-white-manifest.json").write_text(json.dumps(payload))
        self.assertEqual(self.validate()["status"], "INVALID")

    def test_missing_result_is_missing(self):
        shutil.rmtree(self.folder)
        self.assertEqual(self.validate()["status"], "MISSING")

    def test_missing_image_referenced_by_manifest_is_invalid(self):
        self.output.unlink()
        self.assertIn("ARTIFACT_NOT_FOUND", self.validate()["reasons"])

    def test_corrupt_result_hash_is_invalid(self):
        Image.new("RGB", (8, 9), "blue").save(self.output)
        self.assertIn("ARTIFACT_HASH_MISMATCH", self.validate()["reasons"])

    def test_missing_mask_is_invalid(self):
        self.mask.unlink()
        self.assertIn("ARTIFACT_NOT_FOUND", self.validate()["reasons"])

    def test_mask_hash_mismatch_is_invalid(self):
        Image.new("L", (8, 9), 255).save(self.mask)
        self.assertIn("MASK_HASH_MISMATCH", self.validate()["reasons"])

    def test_changed_check_is_stale_even_when_region_ids_match(self):
        self.write_check(extra={"revision": 2})
        self.assertEqual(self.validate()["status"], "STALE")

    def test_changed_source_is_stale(self):
        with patch("central_v2.backend.orchestration.combo_turbo.solids_validator.source_for",
                   return_value=self.source.parent / "other.png"):
            other = self.source.parent / "other.png"
            Image.new("RGB", (8, 9), "blue").save(other)
            item = validate_solids_page(self.manga, "comix", "12", self.page)
        self.assertEqual(item["status"], "STALE")
        self.assertIn("SOURCE_HASH_MISMATCH", item["reasons"])

    def test_changed_approved_regions_are_stale(self):
        self.write_check(ident="roi-new")
        self.assertEqual(self.validate()["status"], "STALE")

    def test_missing_check_is_unverified(self):
        self.check.unlink()
        self.assertEqual(self.validate()["status"], "UNVERIFIED")

    def test_dimensions_must_match(self):
        Image.new("L", (8, 8), 0).save(self.mask)
        payload = json.loads((self.folder / "solid-white-manifest.json").read_text())
        payload["pages"][0]["mask_sha256"] = sha256(self.mask)
        (self.folder / "solid-white-manifest.json").write_text(json.dumps(payload))
        self.assertIn("DIMENSION_MISMATCH", self.validate()["reasons"])

    def test_invalid_manifest_is_invalid(self):
        (self.folder / "solid-white-manifest.json").write_text("not json")
        self.assertEqual(self.validate()["status"], "INVALID")

    def test_repeated_validation_does_not_modify_operational_files(self):
        paths = [self.check, self.output, self.mask, self.folder / "solid-white-manifest.json"]
        before = {path: path.read_bytes() for path in paths}
        first, second = self.validate(), self.validate()
        self.assertEqual(first, second)
        self.assertEqual(before, {path: path.read_bytes() for path in paths})

    def test_stage_symlink_outside_manga_is_invalid(self):
        outside = Path(self.temp.name) / "outside"
        outside.mkdir()
        original = self.folder
        original.rename(original.with_name("hidden"))
        original.symlink_to(outside, target_is_directory=True)
        self.assertIn("PATH_OUTSIDE_ROOT", self.validate()["reasons"])


if __name__ == "__main__":
    unittest.main()
