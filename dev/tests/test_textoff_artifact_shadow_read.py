"""M6 authority and registry-driven shadow validation tests."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from central_v2.backend.orchestration.textoff_merged import artifact_shadow_read
from central_v2.backend.orchestration.textoff_merged.artifact_migration import (
    REGISTRY_PATH, TEXT_OFF_ROOT,
)
from central_v2.backend.orchestration.bubble_sommelier.mapear_results import (
    load_mapear_results,
)
from central_v2.backend.orchestration.bubble_sommelier.query import query as query_sommelier


class TextoffArtifactShadowReadTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.manga = self.root / "manga"
        self.registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))

    def tearDown(self):
        self.temporary.cleanup()

    def stage_paths(self, stage_id, chapter="1"):
        stage = next(item for item in self.registry["stages"]
                     if item["stage_id"] == stage_id)
        base = self.manga / TEXT_OFF_ROOT
        return (base / stage["legacy_path"] / chapter,
                base / stage["target_path"] / chapter)

    def write(self, path, payload):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)

    def mapear_report(self, reason):
        return json.dumps({"pages": [{
            "source": "page.png",
            "styled_balloon_candidates": [{
                "candidate_type": "soft_gradient",
                "features": {"candidate": True, "reason": reason},
            }],
        }]}).encode()

    def test_shadow_covers_the_five_registry_mappings_without_writes(self):
        stage_ids = {
            "auto_cleaner", "mapear", "mapear_input_consolidado",
            "bubble_sommelier", "auto_cleaner_transparencia_basica",
        }
        entries = [item for item in self.registry["stages"]
                   if item["stage_id"] in stage_ids]
        before_registry = REGISTRY_PATH.read_bytes()
        for item in entries:
            legacy, target = self.stage_paths(item["stage_id"])
            self.write(legacy / "sample.bin", b"same")
            self.write(target / "sample.bin", b"same")
        before_files = {p: p.read_bytes() for p in self.manga.rglob("*") if p.is_file()}

        with self.assertLogs(artifact_shadow_read.logger, level="INFO") as output:
            for item in entries:
                artifact_shadow_read.observe_shadow_read(
                    self.manga, item["stage_id"], "1"
                )

        self.assertEqual(len([line for line in output.output if "comparison_status=MATCH" in line]), 5)
        for item in entries:
            self.assertIn(f"stage={item['stage_id']}", " ".join(output.output))
            self.assertIn(f"target_path={item['target_path']}/1", " ".join(output.output))
        self.assertEqual(before_files, {
            p: p.read_bytes() for p in self.manga.rglob("*") if p.is_file()
        })
        self.assertEqual(REGISTRY_PATH.read_bytes(), before_registry)

    def test_legacy_reader_wins_for_match_mismatch_missing_and_invalid_target(self):
        legacy, target = self.stage_paths("mapear")
        legacy_report = self.mapear_report("legacy")
        target_report = self.mapear_report("target")
        self.write(legacy / "styled-balloon-report.json", legacy_report)
        cases = (("MATCH", target_report if legacy_report == target_report else legacy_report),
                 ("MISMATCH", target_report), ("MISSING_TARGET", None),
                 ("MISMATCH", b"target is not a directory"))
        for status, target_payload in cases:
            with self.subTest(status=status, target=target_payload):
                if target.exists():
                    shutil.rmtree(target) if target.is_dir() else target.unlink()
                if target_payload is not None:
                    if target_payload == b"target is not a directory":
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(target_payload)
                    else:
                        self.write(target / "styled-balloon-report.json", target_payload)
                with self.assertLogs(artifact_shadow_read.logger, level="INFO") as output:
                    result = load_mapear_results(self.manga, "1")
                self.assertEqual(result["soft_gradient"]["count"], 1)
                self.assertTrue(any(f"comparison_status={status}" in line
                                    for line in output.output))

    def test_missing_legacy_never_falls_back_to_valid_target(self):
        _, target = self.stage_paths("mapear")
        self.write(target / "styled-balloon-report.json", self.mapear_report("target"))
        with self.assertLogs(artifact_shadow_read.logger, level="WARNING") as output:
            result = load_mapear_results(self.manga, "1")
        self.assertFalse(result["available"])
        self.assertEqual(result["status"], "unavailable")
        self.assertIn("comparison_status=MISSING_LEGACY", " ".join(output.output))
        self.assertFalse(self.stage_paths("mapear")[0].exists())

    def test_both_missing_is_diagnosed_as_missing_legacy_without_traceback(self):
        with self.assertLogs(artifact_shadow_read.logger, level="WARNING") as output:
            artifact_shadow_read.observe_shadow_read(self.manga, "mapear", "1")
        report = " ".join(output.output)
        self.assertIn("comparison_status=MISSING_LEGACY", report)
        self.assertNotIn("SHADOW_READ_ERROR", report)

    def test_sommelier_worklist_does_not_fall_back_to_target_report(self):
        merge = self.manga / "FLUXO_SECUNDARIO/02_MERGE/1/page.png"
        self.write(merge, b"page")
        _, target = self.stage_paths("bubble_sommelier")
        self.write(target / "report.json", b'{"status":"completed"}')
        with self.assertLogs(artifact_shadow_read.logger, level="WARNING") as output:
            result = query_sommelier(self.manga)
        self.assertIsNone(result["chapters"][0]["sommelier"])
        self.assertIn("comparison_status=MISSING_LEGACY", " ".join(output.output))

    def test_shadow_internal_error_is_logged_and_legacy_result_survives(self):
        legacy, target = self.stage_paths("mapear")
        self.write(legacy / "styled-balloon-report.json", self.mapear_report("legacy"))
        self.write(target / "styled-balloon-report.json", self.mapear_report("target"))
        with patch.object(artifact_shadow_read, "validate_stage_chapter",
                          side_effect=RuntimeError("validator failure")):
            with self.assertLogs(artifact_shadow_read.logger, level="ERROR") as output:
                result = load_mapear_results(self.manga, "1")
        self.assertEqual(result["soft_gradient"]["occurrences"][0]["reason"], "legacy")
        self.assertIn("SHADOW_READ_ERROR", " ".join(output.output))

    def test_disabled_shadow_does_not_call_validator(self):
        registry = dict(self.registry)
        registry["new_read_enabled"] = False
        registry_path = self.root / "registry.json"
        registry_path.write_text(json.dumps(registry), encoding="utf-8")
        with patch.object(artifact_shadow_read, "validate_stage_chapter") as validator:
            artifact_shadow_read.observe_shadow_read(
                self.manga, "mapear", "1", registry_path=registry_path
            )
        validator.assert_not_called()


if __name__ == "__main__":
    unittest.main()
