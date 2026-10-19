import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from central_v2.backend.orchestration.textoff_merged import execution
from central_v2.backend.orchestration.textoff_merged.stages import LEVEL1


class TestPatch04B(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='textoff-04b-')
        self.addCleanup(temp.cleanup)
        self.manga = Path(temp.name) / 'comix' / 'Test'
        (self.manga / 'IMG/1').mkdir(parents=True)

    def check_execution(self, numbered=False):
        destinations = []
        with patch.dict(os.environ, {'CENTRAL_V2_LEVEL1_NUMBERED': '1' if numbered else ''}), \
             patch.object(execution, 'validate_selection', return_value=['1']), \
             patch.object(execution.v3, 'is_chapter_merged', return_value=True), \
             patch.object(execution.v3, 'merge_output_dir', return_value=self.manga / 'MERGE/1'), \
             patch.object(execution.v3, 'merge_artifact_files', return_value=[Path('page.png')]), \
             patch.object(execution, 'run_cleaner_v2', side_effect=lambda images, dest, **kw: destinations.append(dest) or {'status': 'ok'}), \
             patch.object(execution, 'mirror_stage_chapter') as mirror:
            result = execution.execute_merged(self.manga, ['1'], lambda *args: None,
                                              output_stage=LEVEL1, include_legacy_level2=False)
        return result, destinations, mirror

    def test_default_preserves_legacy_and_mirror(self):
        result, destinations, mirror = self.check_execution()
        self.assertEqual(result[0]['status'], 'ok')
        self.assertEqual(destinations, [self.manga / 'FLUXO_SECUNDARIO/04_TEXTO_OFF/TO_MERGED_NIVEL_I/1'])
        mirror.assert_called_once_with(self.manga, 'auto_cleaner', '1')

    def test_existing_numbered_override_is_preserved(self):
        result, destinations, mirror = self.check_execution(numbered=True)
        self.assertEqual(result[0]['status'], 'ok')
        self.assertEqual(destinations, [self.manga / 'FLUXO_SECUNDARIO/04_TEXTO_OFF/01_AUTO_CLEANER/1'])
        mirror.assert_not_called()
