"""Verify target-only routing without running image processing or touching real data."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from central_v2.backend.orchestration.textoff_merged import execution
from central_v2.backend.orchestration.textoff_merged.stages import LEVEL1
from central_v2.backend.orchestration.textoff_merged.level1_isolated_destination import (
    numbered_level1_in_isolated_workspace,
    isolated_level1_target,
)


class IsolatedNumberedWriteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="textoff04c-")
        self.addCleanup(self.tmp.cleanup)
        self.manga = Path(self.tmp.name) / "comix" / "Sample"
        (self.manga / "IMG" / "2").mkdir(parents=True)
        (self.manga / ".textoff-isolated-workspace").write_text("04C\\n",encoding="utf-8")

    def run_it(self):
        paths = []
        def fake_clean(images, target, **kwargs):
            target.mkdir(parents=True, exist_ok=True)
            (target / "clean-manifest.json").write_text("test")
            paths.append(target)
            return {"status":"ok"}
        with (patch.dict(os.environ, {"CENTRAL_V2_LEVEL1_NUMBERED": ""}),
              patch.object(execution, "validate_selection", return_value=["2"]),
              patch.object(execution.v3, "is_chapter_merged",return_value=True),
              patch.object(execution.v3, "merge_output_dir",return_value=self.manga / "MERGE/2"),
              patch.object(execution.v3, "merge_artifact_files",return_value=[Path("page.png")]),
              patch.object(execution, "run_cleaner_v2",side_effect=fake_clean),
              patch.object(execution,"mirror_stage_chapter") as mirror):
            result = execution.execute_merged(self.manga, ["2"], lambda *a:None,
                          output_stage=LEVEL1,include_legacy_level2=False)
        return result, paths, mirror

    def test_context_writes_only_numbered(self):
        with numbered_level1_in_isolated_workspace(self.manga):
            result, paths, mirror = self.run_it()
        self.assertEqual(result[0]["status"],"ok")
        self.assertEqual(paths,[self.manga/"FLUXO_SECUNDARIO/04_TEXTO_OFF/01_AUTO_CLEANER/2"])
        mirror.assert_not_called()
        self.assertFalse((self.manga/"FLUXO_SECUNDARIO/04_TEXTO_OFF/TO_MERGED_NIVEL_I/2").exists())

    def test_default_legacy_unchanged(self):
        result, paths, mirror = self.run_it()
        self.assertEqual(result[0]["status"],"ok")
        self.assertEqual(paths,[self.manga/"FLUXO_SECUNDARIO/04_TEXTO_OFF/01_AUTO_CLEANER/2"])
        mirror.assert_called_once()

    def test_unmarked_workspace_denied(self):
        (self.manga / ".textoff-isolated-workspace").unlink()
        with self.assertRaises(ValueError):
            with numbered_level1_in_isolated_workspace(self.manga):
                pass

    def test_context_rejects_different_manga(self):
        other=self.manga.parent/"Other"
        other.mkdir()
        with numbered_level1_in_isolated_workspace(self.manga):
            with self.assertRaises(ValueError):
                isolated_level1_target(other,"2")
        self.assertIsNone(isolated_level1_target(self.manga,"2"))
