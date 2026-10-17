import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from central_v2.backend.orchestration.combo_turbo.glass_validator import validate_glass_page
from central_v2.backend.orchestration.textoff_special.artifacts import sha256
from central_v2.backend.orchestration.textoff_merged.auto_cleaner_check_manifest import (
    MANIFEST_NAME, SCHEMA, manifest_path,
)
from central_v2.backend.orchestration.textoff_merged.artifact_paths import artifact_ref
from central_v2.backend.orchestration.textoff_merged.stages import LEVEL1, LEVEL2, stage_chapter


class ComboGlassValidationTests(unittest.TestCase):
    page = "page-061-065.png"

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.manga = Path(self.temp.name) / "comix" / "Sample"
        self.manga.mkdir(parents=True)
        self.merge = self.manga / "merge"
        self.merge.mkdir()
        self.source = self.merge / self.page
        Image.new("RGB", (8, 9), "white").save(self.source)
        self.l1 = stage_chapter(self.manga, LEVEL1, "12", read_legacy=False)
        self.level1_image = self.l1 / "clean/page-061-065_clean.png"
        self.level1_image.parent.mkdir(parents=True)
        Image.new("RGB", (8, 9), "gray").save(self.level1_image)
        self.glass = stage_chapter(self.manga, LEVEL2, "12", read_legacy=False)
        self.mask = self.glass / "mask/page-061-065_text_mask.png"
        self.mask.parent.mkdir(parents=True)
        Image.new("L", (8, 9), 0).save(self.mask)
        self.output = self.glass / "clean/page-061-065_clean.png"
        self.output.parent.mkdir(parents=True)
        Image.new("RGB", (8, 9), "black").save(self.output)
        self.check = manifest_path(self.manga, "12")
        self.check.parent.mkdir(parents=True)
        self.write_check()
        self.level1_manifest = {"clean_artifacts": ["clean/page-061-065_clean.png"]}
        self.write_glass_manifest()

    def write_check(self, extra=None):
        value = {"schema": SCHEMA, "version": 1, "provider": "comix",
                 "manga": "Sample", "chapter": "12", "source_snapshot": {},
                 "approved_occurrences": []}
        value.update(extra or {})
        self.check.write_text(json.dumps(value), encoding="utf-8")

    def write_glass_manifest(self, provenance=True):
        row = {"source": self.page, "clean": artifact_ref("clean", self.output.name),
               "level1_clean": artifact_ref("clean", self.level1_image.name),
               "mask": artifact_ref("mask", self.mask.name)}
        if provenance:
            row.update(source_sha256=sha256(self.source), level1_sha256=sha256(self.level1_image),
                       result_sha256=sha256(self.output), mask_sha256=sha256(self.mask))
        payload = {"schema_version": 1, "algorithm": "fixture", "integrity_ok": True,
                   "source_stage": LEVEL1, "source_level1_manifest_sha256": "l1-hash",
                   "candidate_source_artifacts": [self.page], "page_results": [row],
                   "source_check_manifest_sha256": sha256(self.check) if provenance else None}
        (self.glass / "json").mkdir(exist_ok=True)
        (self.glass / "json/clean-manifest.json").write_text(json.dumps(payload), encoding="utf-8")

    def validate(self):
        manifest = json.loads((self.glass / "json/clean-manifest.json").read_text())
        with (patch("central_v2.backend.orchestration.combo_turbo.glass_validator._manifest_matches_merge",
                    return_value=True),
              patch("central_v2.backend.orchestration.combo_turbo.glass_validator._stage_manifest",
                    return_value=self.level1_manifest),
              patch("central_v2.backend.orchestration.combo_turbo.glass_validator._stage_manifest_sha256",
                    return_value="l1-hash"),
              patch("central_v2.backend.orchestration.combo_turbo.glass_validator._valid_level2",
                    return_value=(manifest, self.glass,
                                  sha256(self.glass / "json/clean-manifest.json"))),
              patch("central_v2.backend.orchestration.combo_turbo.glass_validator.v3.merge_output_dir",
                    return_value=self.merge)):
            return validate_glass_page(self.manga, "comix", "12", self.page)

    def test_complete_provenance_is_reusable(self):
        item = self.validate()
        self.assertEqual(item["status"], "REUSABLE")
        self.assertTrue(item["check_verified"])
        self.assertTrue(item["integrity_ok"])

    def test_legacy_glass_without_check_hash_is_unverified(self):
        self.write_glass_manifest(provenance=False)
        item = self.validate()
        self.assertEqual(item["status"], "UNVERIFIED")
        self.assertIn("CHECK_HASH_NOT_RECORDED", item["reasons"])
        self.assertIn("ARTIFACT_HASH_NOT_RECORDED", item["reasons"])

    def test_non_candidate_page_is_missing(self):
        payload = json.loads((self.glass / "json/clean-manifest.json").read_text())
        payload["candidate_source_artifacts"] = []
        (self.glass / "json/clean-manifest.json").write_text(json.dumps(payload))
        self.assertEqual(self.validate()["status"], "MISSING")

    def test_check_hash_change_is_stale(self):
        self.write_check(extra={"revision": 2})
        self.assertEqual(self.validate()["status"], "STALE")

    def test_output_hash_mismatch_is_invalid(self):
        Image.new("RGB", (8, 9), "blue").save(self.output)
        self.assertIn("ARTIFACT_HASH_MISMATCH", self.validate()["reasons"])

    def test_mask_hash_mismatch_is_invalid(self):
        Image.new("L", (8, 9), 255).save(self.mask)
        self.assertIn("MASK_HASH_MISMATCH", self.validate()["reasons"])

    def test_mask_symlink_outside_stage_is_rejected(self):
        outside = Path(self.temp.name) / "outside-mask.png"
        Image.new("L", (8, 9), 0).save(outside)
        self.mask.unlink()
        self.mask.symlink_to(outside)
        self.assertIn("ARTIFACT_NOT_FOUND", self.validate()["reasons"])

    def test_missing_mask_is_invalid(self):
        self.mask.unlink()
        self.assertIn("ARTIFACT_NOT_FOUND", self.validate()["reasons"])

    def test_source_hash_mismatch_is_stale(self):
        Image.new("RGB", (8, 9), "blue").save(self.source)
        item = self.validate()
        self.assertEqual(item["status"], "STALE")
        self.assertIn("SOURCE_HASH_MISMATCH", item["reasons"])

    def test_level1_hash_mismatch_is_stale(self):
        Image.new("RGB", (8, 9), "blue").save(self.level1_image)
        item = self.validate()
        self.assertEqual(item["status"], "STALE")
        self.assertIn("SOURCE_HASH_MISMATCH", item["reasons"])

    def test_dimension_mismatch_is_invalid(self):
        Image.new("L", (8, 8), 0).save(self.mask)
        self.assertIn("DIMENSION_MISMATCH", self.validate()["reasons"])

    def test_corrupt_check_manifest_is_invalid(self):
        self.check.write_text("bad json")
        self.assertEqual(self.validate()["status"], "INVALID")

    def test_level1_manifest_change_is_stale(self):
        with patch("central_v2.backend.orchestration.combo_turbo.glass_validator._manifest_matches_merge",
                   return_value=False):
            item = validate_glass_page(self.manga, "comix", "12", self.page)
        self.assertEqual(item["status"], "STALE")


if __name__ == "__main__":
    unittest.main()
