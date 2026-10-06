"""Formal equivalence checks for the M3 TextOff shadow trees."""
import json
from pathlib import Path
import tempfile
import unittest

from central_v2.backend.orchestration.textoff_merged.artifact_migration import (
    REGISTRY_PATH,
    TEXT_OFF_ROOT,
    mirror_stage_chapter,
)
from central_v2.backend.orchestration.textoff_merged.artifact_validation import (
    COMPARISON_STATUSES,
    compare_artifact_trees,
    validate_stage_chapter,
)


class TextoffArtifactValidationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.legacy = self.root / "legacy"
        self.target = self.root / "target"

    def tearDown(self):
        self.temporary.cleanup()

    def write(self, root, relative, data):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def compare(self):
        return compare_artifact_trees(
            self.legacy, self.target, stage="sample", chapter="1",
            legacy_path="legacy/1", target_path="target/1",
        )

    def test_identical_trees_match_with_nested_relative_paths(self):
        contents = {
            "json/clean-manifest.json": b'{"ok":true}\n',
            "clean/page.png": b"image-bytes",
            "mask/page.png": b"mask-bytes",
        }
        for relative, data in contents.items():
            self.write(self.legacy, relative, data)
            self.write(self.target, relative, data)
        result = self.compare()
        self.assertEqual(result["comparison_status"], "MATCH")
        self.assertEqual(
            [item["artifact"] for item in result["artifacts"]],
            sorted(contents),
        )
        self.assertEqual(result["artifacts"][0]["comparison_status"], "MATCH")
        self.assertEqual(result, self.compare())

    def test_same_size_different_contents_mismatch_by_sha256(self):
        self.write(self.legacy, "a.txt", b"ABC")
        self.write(self.target, "a.txt", b"XYZ")
        result = self.compare()
        self.assertEqual(result["artifacts"][0]["size_legacy"], 3)
        self.assertEqual(result["artifacts"][0]["size_target"], 3)
        self.assertNotEqual(result["artifacts"][0]["sha256_legacy"],
                            result["artifacts"][0]["sha256_target"])
        self.assertEqual(result["comparison_status"], "MISMATCH")

    def test_different_sizes_mismatch(self):
        self.write(self.legacy, "a.txt", b"A")
        self.write(self.target, "a.txt", b"AB")
        result = self.compare()
        self.assertEqual(result["artifacts"][0]["size_legacy"], 1)
        self.assertEqual(result["artifacts"][0]["size_target"], 2)
        self.assertEqual(result["comparison_status"], "MISMATCH")

    def test_file_missing_from_target_is_mismatch(self):
        self.write(self.legacy, "nested/a.txt", b"A")
        self.target.mkdir()
        result = self.compare()
        self.assertEqual(result["comparison_status"], "MISMATCH")
        self.assertEqual(result["artifacts"][0]["artifact"], "nested")
        self.assertEqual(result["artifacts"][0]["comparison_status"], "MISMATCH")
        self.assertIn("nested/a.txt", [item["artifact"] for item in result["artifacts"]])

    def test_missing_legacy_root(self):
        self.write(self.target, "a.txt", b"A")
        self.assertEqual(self.compare()["comparison_status"], "MISSING_LEGACY")

    def test_missing_target_root(self):
        self.write(self.legacy, "a.txt", b"A")
        self.assertEqual(self.compare()["comparison_status"], "MISSING_TARGET")

    def test_extra_target_file_is_mismatch(self):
        self.write(self.legacy, "a.txt", b"A")
        self.write(self.target, "a.txt", b"A")
        self.write(self.target, "extra.txt", b"extra")
        result = self.compare()
        self.assertEqual(result["comparison_status"], "MISMATCH")
        self.assertEqual(result["artifacts"][-1]["artifact"], "extra.txt")
        self.assertIsNone(result["artifacts"][-1]["size_legacy"])

    def test_file_directory_type_collision_is_mismatch(self):
        self.write(self.legacy, "node", b"file")
        self.write(self.target, "node/child", b"inside directory")
        result = self.compare()
        self.assertEqual(result["comparison_status"], "MISMATCH")
        node = next(item for item in result["artifacts"] if item["artifact"] == "node")
        self.assertEqual(node["comparison_status"], "MISMATCH")

    def test_empty_file_matches_with_empty_sha256(self):
        self.write(self.legacy, "empty.bin", b"")
        self.write(self.target, "empty.bin", b"")
        result = self.compare()
        self.assertEqual(result["comparison_status"], "MATCH")
        self.assertEqual(result["artifacts"][0]["size_legacy"], 0)
        self.assertEqual(result["artifacts"][0]["sha256_legacy"],
                         "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")

    def test_both_missing_is_an_invalid_comparison_not_not_applicable(self):
        with self.assertRaisesRegex(FileNotFoundError, "Ambos os artefatos"):
            self.compare()

    def test_registry_resolves_all_five_dual_write_mappings(self):
        manga = self.root / "manga"
        expected = {
            "auto_cleaner": ("TO_MERGED_NIVEL_I/1", "01_AUTO_CLEANER/1"),
            "mapear": ("TO_MERGED_NIVEL_III/1", "02_MAPEAR/1"),
            "mapear_input_consolidado": (
                "TO_MERGED_CONSOLIDADO/1", "02_MAPEAR/INPUT_CONSOLIDADO/1"),
            "bubble_sommelier": ("BUBBLE_SOMMELIER/1", "03_BUBBLE_SOMMELIER/1"),
            "auto_cleaner_transparencia_basica": (
                "TO_MERGED_NIVEL_II/1", "05_AUTO_CLEANER_TRANSPARENCIA/BASICA/1"),
        }
        for stage_id, (legacy, target) in expected.items():
            (manga / TEXT_OFF_ROOT / legacy).mkdir(parents=True)
            result = validate_stage_chapter(manga, stage_id, "1")
            self.assertEqual(result["legacy_path"], legacy)
            self.assertEqual(result["target_path"], target)
            self.assertEqual(result["comparison_status"], "MISSING_TARGET")

    def test_integrated_m3_publication_then_m4_validation_matches(self):
        registry_before = REGISTRY_PATH.read_bytes()
        manga = self.root / "manga"
        legacy = manga / TEXT_OFF_ROOT / "TO_MERGED_NIVEL_I" / "1"
        expected = {
            "clean/page.png": b"image\x00payload",
            "json/clean-manifest.json": b'{"integrity_ok":true}\n',
            "empty.bin": b"",
        }
        for relative, data in expected.items():
            self.write(legacy, relative, data)
        legacy_snapshot = {
            path.relative_to(legacy).as_posix(): path.read_bytes()
            for path in legacy.rglob("*") if path.is_file()
        }
        self.assertTrue(mirror_stage_chapter(manga, "auto_cleaner", "1"))
        result = validate_stage_chapter(manga, "auto_cleaner", "1")
        self.assertEqual(result["comparison_status"], "MATCH")
        self.assertEqual(len(result["artifacts"]), len(expected))
        self.assertEqual(legacy_snapshot, {
            path.relative_to(legacy).as_posix(): path.read_bytes()
            for path in legacy.rglob("*") if path.is_file()
        })
        registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        active_ids = {
            "auto_cleaner", "mapear", "mapear_input_consolidado",
            "bubble_sommelier", "auto_cleaner_transparencia_basica",
        }
        self.assertTrue(all(
            not stage["validated"] for stage in registry["stages"]
            if stage["stage_id"] in active_ids
        ))
        self.assertEqual(REGISTRY_PATH.read_bytes(), registry_before)

    def test_non_dual_write_stage_is_not_applicable(self):
        result = validate_stage_chapter(self.root / "manga", "auto_cleaner_check", "1")
        self.assertEqual(result["comparison_status"], "NOT_APPLICABLE")
        self.assertEqual(result["artifacts"], [])

    def test_contract_taxonomy_is_registry_taxonomy(self):
        self.assertEqual(COMPARISON_STATUSES, {
            "MATCH", "STRUCTURAL_MATCH", "MISMATCH", "MISSING_LEGACY",
            "MISSING_TARGET", "NOT_APPLICABLE",
        })
        # No current exception allowlist exists, so no actual comparison emits it.
        self.write(self.legacy, "a.txt", b"same")
        self.write(self.target, "a.txt", b"same")
        result = self.compare()
        self.assertNotEqual(result["comparison_status"], "STRUCTURAL_MATCH")


if __name__ == "__main__":
    unittest.main()
