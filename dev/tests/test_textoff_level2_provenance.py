import tempfile
import unittest
from pathlib import Path
import json
from unittest.mock import patch

from central_v2.backend.orchestration.textoff_merged import level2
from central_v2.backend.orchestration.textoff_merged.artifact_paths import artifact_ref
from central_v2.backend.orchestration.textoff_merged.level2_provenance import (
    assert_report_artifacts_current, validate_protection_provenance,
    validate_report_provenance,
)
from central_v2.backend.orchestration.textoff_merged.level2_validation import (
    promote_stage, validated_candidate_pages,
)
from central_v2.backend.orchestration.textoff_special.artifacts import sha256


class Level2ProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.authority = {"kind": "CHECK", "path": "check.json", "sha256": "a" * 64,
                          "revision": 7}
        self.occurrences = {"page.png": [{"id": "manual-1", "tipo": "residuo"}]}
        self.page = {"source": "page.png", "source_sha256": "a" * 64,
                     "level1_sha256": "b" * 64, "result_sha256": "c" * 64,
                     "mask_sha256": "d" * 64, "level1_report_sha256": "e" * 64,
                     "level1_mask_sha256": "f" * 64, "deferred_mask_sha256": None,
                     "protection_source": dict(self.authority),
                     "protected_occurrence_ids": ["manual-1"],
                     "protected_types_applied": ["residuo"], "protected_types": ["residuo"],
                     "protected_occurrences": 1, "protected_pixels": 2,
                     "mask_pixels_before_protection": 12,
                     "mask_pixels_after_protection": 10, "mask_pixels": 10}
        self.report = {"source_level1_manifest_sha256": "1" * 64,
                       "protected_occurrences": 1, "protected_pixels": 2,
                       "mask_pixels_before_protection": 12,
                       "mask_pixels_after_protection": 10,
                       "protected_types": ["residuo"]}

    def validate(self, page=None, occurrences=None):
        row = page or self.page
        validate_report_provenance([row], "1" * 64,
                                   self.report["source_level1_manifest_sha256"], "12")
        validate_protection_provenance(self.report, [row], self.authority,
                                       occurrences or self.occurrences, "12")

    def test_valid_provenance_is_accepted(self):
        self.validate()

    def test_unknown_protection_id_is_rejected(self):
        row = {**self.page, "protected_occurrence_ids": ["unknown"]}
        with self.assertRaisesRegex(ValueError, "Cap. 12 página page.png campo protected_occurrence_ids"):
            self.validate(row)

    def test_type_source_and_missing_metadata_are_rejected(self):
        for field, value in (("protection_source", {**self.authority, "revision": 8}),
                             ("protected_pixels", None)):
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "Cap. 12"):
                self.validate({**self.page, field: value})
        row = {**self.page, "protected_types_applied": ["other"], "protected_types": ["other"]}
        with self.assertRaisesRegex(ValueError, "protected_types_applied"):
            self.validate(row)
        row = dict(self.page)
        del row["protection_source"]
        with self.assertRaisesRegex(ValueError, "protection_source"):
            self.validate(row)

    def test_page_pixel_counts_must_be_coherent(self):
        with self.assertRaisesRegex(ValueError, "protected_pixels.*contagens"):
            self.validate({**self.page, "protected_pixels": 3})

    def test_changed_check_hash_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "check.json"
            source.write_text("before")
            captured = {"path": "check.json", "sha256": sha256(source)}
            source.write_text("after")
            with self.assertRaisesRegex(ValueError, "mudou"):
                level2._assert_protection_source_current(Path(temp), captured)

    def test_changed_real_source_hash_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source_dir, level1_dir, output = (root / "source", root / "level1", root / "output")
            for folder in (source_dir, level1_dir, output):
                folder.mkdir()
            source = source_dir / "page.png"
            level1 = level1_dir / artifact_ref("clean", "page_clean.png")
            mask1 = level1_dir / artifact_ref("mask", "page_transparent.png")
            report1 = level1_dir / "json/level1-balloon-report.json"
            result = level1
            mask = output / artifact_ref("mask", "page_text.png")
            for path in (level1, mask1, report1, mask):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"artifact")
            report1.write_text(json.dumps({"pages": [{"source": "page.png",
                                                       "transparent_mask_artifact": mask1.relative_to(level1_dir).as_posix()}]}))
            source.write_bytes(b"source")
            row = {"source": "page.png", "level1_clean": artifact_ref("clean", "page_clean.png"),
                   "clean": None, "mask": artifact_ref("mask", "page_text.png"),
                   "source_sha256": sha256(source), "level1_sha256": sha256(level1),
                   "result_sha256": sha256(result), "mask_sha256": sha256(mask),
                   "level1_report_sha256": sha256(report1), "level1_mask_sha256": sha256(mask1),
                   "deferred_mask_sha256": None}
            source.write_bytes(b"altered")
            with self.assertRaisesRegex(ValueError, "Artefatos.*mudaram"):
                assert_report_artifacts_current({"pages": [row]}, source_dir, level1_dir, output)

    def test_changed_outside_mask_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = "page.png"
            clean = artifact_ref("clean", "page_clean.png")
            mask = artifact_ref("mask", "page_mask.png")
            (root / clean).parent.mkdir(parents=True)
            (root / clean).write_bytes(b"clean")
            (root / mask).parent.mkdir(parents=True)
            (root / mask).write_bytes(b"mask")
            row = {"source": source, "level1_clean": clean, "clean": None, "mask": mask,
                   "changed_pixels": 0, "mask_pixels": 1, "changed_outside_mask": 1}
            with self.assertRaisesRegex(RuntimeError, "violou a máscara"):
                validated_candidate_pages({"pages": [row], "pages_analyzed": 1},
                                          [source], root, root)

    def test_promote_failure_restores_previous_stage(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            staged, target = root / "staged", root / "target"
            staged.mkdir()
            target.mkdir()
            (staged / "new").write_text("new")
            (target / "old").write_text("old")
            replace = __import__("os").replace
            calls = 0

            def fail_second(source, destination):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("promote failed")
                replace(source, destination)

            with patch("central_v2.backend.orchestration.textoff_merged.level2_validation.os.replace",
                       side_effect=fail_second), self.assertRaisesRegex(OSError, "promote failed"):
                promote_stage(staged, target)
            self.assertEqual((target / "old").read_text(), "old")


if __name__ == "__main__":
    unittest.main()
