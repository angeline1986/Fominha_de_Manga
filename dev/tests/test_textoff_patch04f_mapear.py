"""Mapear target-only routing contract tests, without loading the detector."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from central_v2.backend.orchestration.textoff_merged.mapear_isolated_destination import (
    isolated_mapear_target, numbered_mapear_in_isolated_workspace,
)


class Mapear04FTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='textoff04f-')
        self.addCleanup(self.tmp.cleanup)
        self.manga = Path(self.tmp.name) / 'comix' / 'Exemplo'
        self.manga.mkdir(parents=True)
        (self.manga / '.textoff-isolated-workspace').write_text('04F\n')

    def test_default_inactive(self):
        self.assertIsNone(isolated_mapear_target(self.manga, '2'))

    def test_numbered_routing(self):
        with numbered_mapear_in_isolated_workspace(self.manga):
            result = isolated_mapear_target(self.manga, '2')
        self.assertEqual(result, self.manga / 'FLUXO_SECUNDARIO/04_TEXTO_OFF/02_MAPEAR/2')
        self.assertIsNone(isolated_mapear_target(self.manga, '2'))

    def test_reject_other_manga(self):
        other = self.manga.parent / 'Outra'
        other.mkdir()
        with numbered_mapear_in_isolated_workspace(self.manga):
            with self.assertRaises(ValueError):
                isolated_mapear_target(other, '2')

    def test_reject_unmarked_workspace(self):
        (self.manga / '.textoff-isolated-workspace').unlink()
        with self.assertRaises(ValueError):
            with numbered_mapear_in_isolated_workspace(self.manga):
                pass
