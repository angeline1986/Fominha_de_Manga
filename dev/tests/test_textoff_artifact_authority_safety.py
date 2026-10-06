"""M7 authority failures and explicit legacy rollback remain observable."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from central_v2.backend.orchestration.textoff_merged import artifact_migration
from central_v2.backend.orchestration.textoff_merged.artifact_validation import validate_stage_chapter
from central_v2.backend.orchestration.bubble_sommelier.mapear_results import load_mapear_results


class ArtifactAuthoritySafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manga = self.root / "manga"
        self.manga.mkdir()
        self.registry_path = self.root / "registry.json"
        self.registry = json.loads(artifact_migration.REGISTRY_PATH.read_text())
        for stage in self.registry["stages"]:
            if stage.get("dual_write"):
                stage["read_authority"] = "target"
        self.registry["read_authority"] = "target"
        self.save_registry()
        self.patch_registry = patch.object(artifact_migration, "REGISTRY_PATH", self.registry_path)
        self.patch_registry.start()
        self.addCleanup(self.patch_registry.stop)

    def save_registry(self):
        self.registry_path.write_text(json.dumps(self.registry))

    def stage_dir(self, side):
        entry = next(item for item in self.registry["stages"] if item["stage_id"] == "mapear")
        return self.manga / "FLUXO_SECUNDARIO/04_TEXTO_OFF" / entry[f"{side}_path"] / "1"

    def write_report(self, path, reason):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"pages": [{"source": "p.png", "styled_balloon_candidates": [{
            "candidate_type": "soft_gradient", "features": {"candidate": True, "reason": reason},
        }]}]}))

    def test_missing_target_does_not_fall_back_to_legacy(self):
        legacy = self.stage_dir("legacy") / "styled-balloon-report.json"
        self.write_report(legacy, "legacy-only")
        with self.assertLogs(artifact_migration.logger, level="ERROR") as logs:
            result = load_mapear_results(self.manga, "1")
        self.assertFalse(result["available"])
        self.assertIn("status=MISSING_TARGET", " ".join(logs.output))
        self.assertTrue(legacy.is_file())
        self.assertFalse(self.stage_dir("target").exists())

    def test_invalid_target_does_not_fall_back_to_legacy(self):
        legacy = self.stage_dir("legacy") / "styled-balloon-report.json"
        self.write_report(legacy, "legacy-only")
        target = self.stage_dir("target")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"not a directory")
        with self.assertLogs(artifact_migration.logger, level="ERROR") as logs:
            result = load_mapear_results(self.manga, "1")
        self.assertFalse(result["available"])
        self.assertIn("status=INVALID_TARGET", " ".join(logs.output))
        self.assertEqual(target.read_bytes(), b"not a directory")

    def test_invalid_target_report_does_not_fall_back_to_legacy(self):
        legacy = self.stage_dir("legacy") / "styled-balloon-report.json"
        self.write_report(legacy, "legacy-only")
        target_report = self.stage_dir("target") / "styled-balloon-report.json"
        target_report.parent.mkdir(parents=True, exist_ok=True)
        target_report.write_text("not-json")
        result = load_mapear_results(self.manga, "1")
        self.assertEqual(result["status"], "invalid")
        self.assertEqual(result["soft_gradient"]["count"], 0)
        self.assertTrue(legacy.is_file())

    def test_rollback_is_explicit_and_reads_legacy_without_mutation(self):
        self.registry["read_authority"] = "legacy"
        for stage in self.registry["stages"]:
            if stage.get("dual_write"):
                stage["read_authority"] = "legacy"
        self.save_registry()
        for side, reason in (("legacy", "legacy-authority"), ("target", "target-only")):
            self.write_report(self.stage_dir(side) / "styled-balloon-report.json", reason)
        before = {path.relative_to(self.manga): path.read_bytes()
                  for path in self.manga.rglob("*") if path.is_file()}
        result = load_mapear_results(self.manga, "1")
        after = {path.relative_to(self.manga): path.read_bytes()
                 for path in self.manga.rglob("*") if path.is_file()}
        self.assertEqual(result["soft_gradient"]["occurrences"][0]["reason"], "legacy-authority")
        self.assertEqual(before, after)
        self.assertTrue(self.registry["legacy_read_enabled"])
        self.assertTrue(self.registry["new_read_enabled"])
        self.assertTrue(self.registry["dual_write_enabled"])

    def test_m4_comparison_allows_target_authority_with_missing_legacy(self):
        target = self.stage_dir("target") / "marker.txt"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("target-valid")
        result = validate_stage_chapter(
            self.manga, "mapear", "1", registry_path=self.registry_path
        )
        self.assertEqual(result["comparison_status"], "MISSING_LEGACY")
        self.assertEqual(target.read_text(), "target-valid")


if __name__ == "__main__":
    unittest.main()
