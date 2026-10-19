"""Testes de isolamento do destino da Transparência Básica."""
import tempfile
import unittest
from pathlib import Path

from central_v2.backend.orchestration.textoff_merged.level2_isolated_destination import (
    isolated_level2_target, numbered_level2_in_isolated_workspace,
)


class Level2Patch04HTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="textoff04h-")
        self.addCleanup(self.tmp.cleanup)
        self.manga = Path(self.tmp.name) / "comix" / "Manga Teste"
        self.manga.mkdir(parents=True)
        (self.manga / ".textoff-isolated-workspace").write_text("04H\\n", encoding="utf-8")

    def test_default_inactive(self):
        self.assertIsNone(isolated_level2_target(self.manga, "2"))

    def test_numbered_destination_and_context_cleanup(self):
        with numbered_level2_in_isolated_workspace(self.manga):
            target = isolated_level2_target(self.manga, "2")
            self.assertEqual(
                target,
                self.manga / "FLUXO_SECUNDARIO/04_TEXTO_OFF"
                / "05_AUTO_CLEANER_TRANSPARENCIA/BASICA/2",
            )
        self.assertIsNone(isolated_level2_target(self.manga, "2"))

    def test_reject_other_manga(self):
        other = self.manga.parent / "Other"
        other.mkdir()
        with numbered_level2_in_isolated_workspace(self.manga):
            with self.assertRaises(ValueError):
                isolated_level2_target(other, "2")

    def test_reject_unmarked_workspace(self):
        (self.manga / ".textoff-isolated-workspace").unlink()
        with self.assertRaises(ValueError):
            with numbered_level2_in_isolated_workspace(self.manga):
                pass
