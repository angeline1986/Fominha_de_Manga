"""Contrato: autoridade de leitura não altera o destino da execução Sommelier."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from central_v2.backend.orchestration.textoff_merged import artifact_migration
from central_v2.backend.orchestration.bubble_sommelier import artifacts, execution


class SommelierWriteAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.manga = Path(self.tmp.name) / "obra"
        self.manga.mkdir()
        registry = json.loads(artifact_migration.REGISTRY_PATH.read_text())
        registry["read_authority"] = "target"
        for entry in registry["stages"]:
            if entry.get("dual_write"):
                entry["read_authority"] = "target"
        local = Path(self.tmp.name) / "registry.json"
        local.write_text(json.dumps(registry))
        guard = patch.object(artifact_migration, "REGISTRY_PATH", local)
        guard.start()
        self.addCleanup(guard.stop)
        self.legacy = self.manga / "FLUXO_SECUNDARIO/04_TEXTO_OFF/BUBBLE_SOMMELIER/1"
        self.target = self.manga / "FLUXO_SECUNDARIO/04_TEXTO_OFF/03_BUBBLE_SOMMELIER/1"

    def test_write_legacy_read_target(self):
        self.target.mkdir(parents=True)
        self.assertEqual(artifacts.execution_dir(self.manga, "1"), self.target)
        self.assertEqual(artifacts.execution_write_dir(self.manga, "1"), self.legacy)
        self.assertEqual(artifacts.report_path(self.manga, "1"), self.target / "report.json")

    def test_target_missing_fails_read_but_write_path_stays_legacy(self):
        self.assertEqual(artifacts.execution_write_dir(self.manga, "1"), self.legacy)
        with self.assertRaises(artifact_migration.ArtifactAuthorityUnavailable):
            artifacts.execution_dir(self.manga, "1")

    def test_executor_publishes_legacy_then_mirrors(self):
        self.target.mkdir(parents=True)
        payload = {"profile_id": "p", "checkpoints": {"result": {
            "pages": 1, "crops": 1, "coverageGe075": 1, "candidates": 0
        }}}
        observed = []
        def fake_run(_source, output, _profile, **_kwargs):
            observed.append(Path(output))
            Path(output, "report.json").write_text(json.dumps(payload))
        with (
            patch.object(execution, "run", side_effect=fake_run),
            patch.object(execution, "validate_profile_id", return_value="p"),
            patch.object(execution, "validate_report", side_effect=lambda report, profile: report),
            patch.object(execution, "incorporate_mapear_results", side_effect=lambda report, *_: report),
            patch.object(execution, "mirror_stage_chapter") as mirror,
        ):
            result = execution.execute(self.manga, ["1"], lambda *_: None, "p")
        self.assertEqual(observed, [self.legacy])
        self.assertEqual(result[0]["chapter"], "1")
        self.assertTrue((self.legacy / "report.json").is_file())
        mirror.assert_called_once_with(self.manga, "bubble_sommelier", "1")


if __name__ == "__main__":
    unittest.main()
