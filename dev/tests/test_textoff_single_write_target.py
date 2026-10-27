"""Future TextOff runs use one numbered tree and retain legacy-only reads."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from central_v2.backend.orchestration.textoff_merged import artifact_migration
from central_v2.backend.orchestration.textoff_merged.artifact_migration import (
    mirror_stage_chapter,
)
from central_v2.backend.orchestration.textoff_merged.stages import stage_chapter
from central_v2.backend.orchestration.textoff_merged.write_destination import planned_write_chapter


STAGES = {
    "auto_cleaner": ("TO_MERGED_NIVEL_I", "01_AUTO_CLEANER"),
    "mapear": ("TO_MERGED_NIVEL_III", "02_MAPEAR"),
    "mapear_input_consolidado": (
        "TO_MERGED_CONSOLIDADO", "02_MAPEAR/INPUT_CONSOLIDADO"),
    "bubble_sommelier": ("BUBBLE_SOMMELIER", "03_BUBBLE_SOMMELIER"),
    "auto_cleaner_transparencia_basica": (
        "TO_MERGED_NIVEL_II", "05_AUTO_CLEANER_TRANSPARENCIA/BASICA"),
}


class SingleWriteTargetTests(unittest.TestCase):
    def test_invalid_single_write_contract_never_routes_to_legacy(self):
        registry = json.loads(artifact_migration.REGISTRY_PATH.read_text())
        registry["dual_write_enabled"] = True
        with tempfile.TemporaryDirectory() as root, \
             patch.object(artifact_migration, "_read_registry", return_value=registry):
            manga = Path(root) / "obra"
            with self.assertRaises(ValueError):
                stage_chapter(manga, "TO_MERGED_NIVEL_I", "1", read_legacy=False)
            with self.assertRaises(ValueError):
                planned_write_chapter(manga, "auto_cleaner", "1")

    def test_numbered_write_and_legacy_only_read(self):
        with tempfile.TemporaryDirectory() as root:
            manga = Path(root) / "obra"
            base = manga / "FLUXO_SECUNDARIO/04_TEXTO_OFF"
            for stage_id, (old, new) in STAGES.items():
                with self.subTest(stage=stage_id):
                    old_dir, new_dir = base / old / "1", base / new / "1"
                    old_dir.mkdir(parents=True, exist_ok=True)
                    (old_dir / "marker").write_text("legacy")
                    self.assertEqual(stage_chapter(manga, old, "1"), old_dir)
                    self.assertEqual(stage_chapter(manga, old, "1", read_legacy=False), new_dir)
                    self.assertEqual(planned_write_chapter(manga, stage_id, "1"), new_dir)
                    self.assertFalse(mirror_stage_chapter(manga, stage_id, "1"))
                    self.assertFalse(new_dir.exists())
                    new_dir.mkdir(parents=True)
                    (new_dir / "marker").write_text("new")
                    self.assertEqual(stage_chapter(manga, old, "1"), new_dir)
                    self.assertEqual((old_dir / "marker").read_text(), "legacy")

    def test_numbered_destination_cannot_point_to_legacy_folder(self):
        with tempfile.TemporaryDirectory() as root:
            manga = Path(root) / "obra"
            base = manga / "FLUXO_SECUNDARIO/04_TEXTO_OFF"
            old = base / "TO_MERGED_NIVEL_I"
            old.mkdir(parents=True)
            (base / "01_AUTO_CLEANER").symlink_to(old, target_is_directory=True)
            with self.assertRaises(ValueError):
                stage_chapter(manga, "TO_MERGED_NIVEL_I", "1", read_legacy=False)


if __name__ == "__main__":
    unittest.main()
