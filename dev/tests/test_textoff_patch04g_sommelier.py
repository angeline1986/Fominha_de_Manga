"""Patch 04G: focused destination and mirror regression tests."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from central_v2.backend.orchestration.bubble_sommelier import execution
from central_v2.backend.orchestration.bubble_sommelier.sommelier_isolated_destination import (
    numbered_sommelier_in_isolated_workspace, isolated_sommelier_target,
)


class Sommelier04GTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="textoff04g-")
        self.addCleanup(self.temp.cleanup)
        self.manga = Path(self.temp.name) / "comix" / "Sample"
        self.manga.mkdir(parents=True)
        (self.manga / ".textoff-isolated-workspace").write_text("04G")

    def test_context_target_and_default(self):
        self.assertIsNone(isolated_sommelier_target(self.manga, "2"))
        with numbered_sommelier_in_isolated_workspace(self.manga):
            result = isolated_sommelier_target(self.manga, "2")
            self.assertEqual(result, self.manga / "FLUXO_SECUNDARIO/04_TEXTO_OFF/03_BUBBLE_SOMMELIER/2")
        self.assertIsNone(isolated_sommelier_target(self.manga, "2"))

    def test_other_manga_blocked(self):
        other = self.manga.parent / "Other"
        other.mkdir()
        with numbered_sommelier_in_isolated_workspace(self.manga):
            with self.assertRaises(ValueError):
                isolated_sommelier_target(other, "2")

    def test_unmarked_workspace_blocked(self):
        (self.manga / ".textoff-isolated-workspace").unlink()
        with self.assertRaises(ValueError):
            with numbered_sommelier_in_isolated_workspace(self.manga):
                pass

    def test_invalid_chapter_rejected(self):
        with numbered_sommelier_in_isolated_workspace(self.manga):
            with self.assertRaises(ValueError):
                isolated_sommelier_target(self.manga, "../2")
