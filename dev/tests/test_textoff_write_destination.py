"""Patch 04A: destination planning never changes operational files."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from central_v2.backend.orchestration.textoff_merged import artifact_migration
from central_v2.backend.orchestration.textoff_merged.write_destination import planned_write_chapter


class WriteDestinationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.manga = Path(self.tmp.name) / "comix" / "fixture"
        self.manga.mkdir(parents=True)
        original = json.loads(artifact_migration.REGISTRY_PATH.read_text(encoding="utf-8"))
        self.registry = original
        self.patch_reader = patch.object(artifact_migration, "_read_registry", return_value=self.registry)
        self.patch_reader.start()
        self.addCleanup(self.patch_reader.stop)

    def test_five_stages_default_and_preview(self):
        expected = {
            "auto_cleaner": ("TO_MERGED_NIVEL_I", "01_AUTO_CLEANER"),
            "auto_cleaner_transparencia_basica": (
                "TO_MERGED_NIVEL_II", "05_AUTO_CLEANER_TRANSPARENCIA/BASICA"),
            "mapear": ("TO_MERGED_NIVEL_III", "02_MAPEAR"),
            "mapear_input_consolidado": (
                "TO_MERGED_CONSOLIDADO", "02_MAPEAR/INPUT_CONSOLIDADO"),
            "bubble_sommelier": ("BUBBLE_SOMMELIER", "03_BUBBLE_SOMMELIER"),
        }
        for stage, (old, new) in expected.items():
            with self.subTest(stage=stage):
                self.assertEqual(planned_write_chapter(self.manga, stage, "1"),
                                 self.manga / "FLUXO_SECUNDARIO/04_TEXTO_OFF" / old / "1")
                self.assertEqual(planned_write_chapter(self.manga, stage, "1", preview_target=True),
                                 self.manga / "FLUXO_SECUNDARIO/04_TEXTO_OFF" / new / "1")
        self.assertEqual(list(self.manga.rglob("*")), [])

    def test_reject_invalid_stage_and_chapter(self):
        for bad in ("../x", "a/b", ".", "..", "", "a\\b"):
            with self.subTest(chapter=bad), self.assertRaises(ValueError):
                planned_write_chapter(self.manga, "mapear", bad)
        with self.assertRaises(ValueError):
            planned_write_chapter(self.manga, "invalid", "1")
        with self.assertRaises(ValueError):
            planned_write_chapter(self.manga, "auto_cleaner_check", "1")

    def test_fail_closed_when_registry_mode_changes(self):
        self.registry["dual_write_enabled"] = False
        with self.assertRaises(ValueError):
            planned_write_chapter(self.manga, "mapear", "1")

    def test_reject_symlink_escape(self):
        base = self.manga / "FLUXO_SECUNDARIO/04_TEXTO_OFF"
        base.mkdir(parents=True)
        (base / "02_MAPEAR").symlink_to(Path(self.tmp.name), target_is_directory=True)
        with self.assertRaises(ValueError):
            planned_write_chapter(self.manga, "mapear", "1", preview_target=True)


if __name__ == "__main__":
    unittest.main()
