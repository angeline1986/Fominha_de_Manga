"""Tests for controlled TextOff artifact shadow writes."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from central_v2.backend.orchestration.textoff_merged import artifact_migration
from central_v2.backend.orchestration.textoff_merged.stages import LEVEL1, stage_chapter


REGISTRY_PATH = artifact_migration.REGISTRY_PATH


class TextoffArtifactDualWriteTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        payload = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        payload["migration_mode"] = "dual_write"
        payload["dual_write_enabled"] = True
        for stage in payload["stages"]:
            stage["dual_write"] = stage["stage_id"] in {
                "auto_cleaner", "mapear", "mapear_input_consolidado",
                "bubble_sommelier", "auto_cleaner_transparencia_basica",
            }
        self.registry_path = self.root / "registry.json"
        self.registry_path.write_text(json.dumps(payload), encoding="utf-8")
        self.registry_patch = patch.object(artifact_migration, "REGISTRY_PATH", self.registry_path)
        self.registry_patch.start()
        self.addCleanup(self.registry_patch.stop)
        self.addCleanup(self.temporary.cleanup)
        self.manga = self.root / "manga"
        self.textoff = self.manga / "FLUXO_SECUNDARIO" / "04_TEXTO_OFF"

    def _write_legacy_tree(self, stage, chapter="1"):
        legacy_root = self.textoff / stage / chapter
        files = {
            "clean/a.png": b"clean-image\x00bytes",
            "json/clean-manifest.json": b'{"integrity_ok":true}\n',
            "mask/a.png": b"mask-image\x00bytes",
        }
        for relative, contents in files.items():
            path = legacy_root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(contents)
        return legacy_root, files

    def test_auto_cleaner_tree_is_mirrored_byte_for_byte(self):
        legacy, files = self._write_legacy_tree("TO_MERGED_NIVEL_I")
        self.assertTrue(artifact_migration.mirror_stage_chapter(
            self.manga, "auto_cleaner", "1"))
        target = self.textoff / "01_AUTO_CLEANER" / "1"
        self.assertEqual(sorted(path.relative_to(target).as_posix()
                                for path in target.rglob("*") if path.is_file()),
                         sorted(files))
        for relative, contents in files.items():
            self.assertEqual((target / relative).read_bytes(), contents)
            self.assertEqual((legacy / relative).read_bytes(), contents)

    def test_registry_is_active_but_stage_read_helper_stays_on_legacy(self):
        registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        self.assertEqual(registry["migration_mode"], "dual_write")
        self.assertIs(registry["legacy_read_enabled"], True)
        self.assertIs(registry["new_read_enabled"], False)
        self.assertIs(registry["dual_write_enabled"], True)
        for stage_id in ("auto_cleaner", "mapear", "mapear_input_consolidado",
                         "bubble_sommelier", "auto_cleaner_transparencia_basica"):
            self.assertTrue(next(stage for stage in registry["stages"]
                                 if stage["stage_id"] == stage_id)["dual_write"])
        legacy = self.textoff / "TO_MERGED_NIVEL_I" / "1"
        target = self.textoff / "01_AUTO_CLEANER" / "1"
        legacy.mkdir(parents=True)
        target.mkdir(parents=True)
        self.assertEqual(stage_chapter(self.manga, LEVEL1, "1"), legacy)

    def test_consolidated_is_nested_under_mapear_input(self):
        self._write_legacy_tree("TO_MERGED_CONSOLIDADO")
        self.assertTrue(artifact_migration.mirror_stage_chapter(
            self.manga, "mapear_input_consolidado", "1"))
        target = self.textoff / "02_MAPEAR" / "INPUT_CONSOLIDADO" / "1"
        self.assertEqual((target / "json/clean-manifest.json").read_bytes(),
                         b'{"integrity_ok":true}\n')
        self.assertFalse((self.textoff / "02_MAPEAR" / "1").exists())

    def test_mapear_and_transparency_basic_use_their_declared_targets(self):
        for stage_id, legacy_name, target_name in (
            ("mapear", "TO_MERGED_NIVEL_III", "02_MAPEAR"),
            ("auto_cleaner_transparencia_basica", "TO_MERGED_NIVEL_II",
             "05_AUTO_CLEANER_TRANSPARENCIA/BASICA"),
        ):
            with self.subTest(stage=stage_id):
                legacy, _ = self._write_legacy_tree(legacy_name)
                self.assertTrue(artifact_migration.mirror_stage_chapter(
                    self.manga, stage_id, "1"))
                target = self.textoff / target_name / "1"
                self.assertEqual(
                    (target / "json/clean-manifest.json").read_bytes(),
                    (legacy / "json/clean-manifest.json").read_bytes(),
                )
                self.assertEqual((target / "clean/a.png").read_bytes(),
                                 (legacy / "clean/a.png").read_bytes())

    def test_ineligible_check_residue_and_previews_are_not_mirrored(self):
        for stage_id, legacy in (
            ("auto_cleaner_check", None),
            ("residue_occurrences", "RESIDUE_OCCURRENCES"),
            ("transparencia_normal", None),
            ("transparencia_legada", None),
            ("pincel_degrade", None),
            ("pincel_artistico", None),
            ("pincel_suave", None),
        ):
            with self.subTest(stage=stage_id):
                if legacy:
                    self._write_legacy_tree(legacy)
                self.assertFalse(artifact_migration.mirror_stage_chapter(
                    self.manga, stage_id, "1"))
        self.assertFalse((self.textoff / "04_AUTO_CLEANER_CHECK").exists())
        self.assertFalse((self.textoff / "04_AUTO_CLEANER_CHECK" /
                          "RESIDUE_OCCURRENCES").exists())

    def test_target_failure_is_explicit_and_keeps_legacy_tree(self):
        legacy, _ = self._write_legacy_tree("TO_MERGED_CONSOLIDADO")
        target_parent = self.textoff / "02_MAPEAR" / "INPUT_CONSOLIDADO"
        target_parent.parent.mkdir(parents=True)
        target_parent.write_bytes(b"blocks target directory creation")
        with self.assertRaisesRegex(artifact_migration.ArtifactMirrorError,
                                    "DUAL_WRITE_MIRROR_FAILED.*mapear_input_consolidado"):
            artifact_migration.mirror_stage_chapter(
                self.manga, "mapear_input_consolidado", "1")
        self.assertEqual((legacy / "json/clean-manifest.json").read_bytes(),
                         b'{"integrity_ok":true}\n')

    def test_shadow_refresh_replaces_prior_copy_without_touching_legacy(self):
        legacy, _ = self._write_legacy_tree("BUBBLE_SOMMELIER")
        target = self.textoff / "03_BUBBLE_SOMMELIER" / "1"
        stale = target / "old-output.json"
        stale.parent.mkdir(parents=True)
        stale.write_text("old shadow", encoding="utf-8")
        self.assertTrue(artifact_migration.mirror_stage_chapter(
            self.manga, "bubble_sommelier", "1"))
        self.assertFalse(stale.exists())
        self.assertEqual((target / "clean/a.png").read_bytes(), b"clean-image\x00bytes")
        self.assertTrue((legacy / "clean/a.png").is_file())


if __name__ == "__main__":
    unittest.main()
