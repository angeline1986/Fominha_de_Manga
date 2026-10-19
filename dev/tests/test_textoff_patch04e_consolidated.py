import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from central_v2.backend.orchestration.textoff_merged import consolidated as con
from central_v2.backend.orchestration.textoff_merged.consolidated_isolated_destination import (
    numbered_consolidated_in_isolated_workspace, isolated_consolidated_target)


class Consolidado04ETests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='textoff04e-')
        self.addCleanup(self.temp.cleanup)
        self.manga = Path(self.temp.name) / 'comix' / 'Teste'
        self.manga.mkdir(parents=True)
        (self.manga / '.textoff-isolated-workspace').write_text('04E')

    def test_mode_off_by_default(self):
        self.assertIsNone(isolated_consolidated_target(self.manga, '2'))

    def test_reject_workspace_without_marker(self):
        (self.manga / '.textoff-isolated-workspace').unlink()
        with self.assertRaises(ValueError):
            with numbered_consolidated_in_isolated_workspace(self.manga):
                pass

    def test_target_routing_and_other_manga_denied(self):
        with numbered_consolidated_in_isolated_workspace(self.manga):
            path=isolated_consolidated_target(self.manga,'2')
            self.assertEqual(path,self.manga/'FLUXO_SECUNDARIO/04_TEXTO_OFF/02_MAPEAR/INPUT_CONSOLIDADO/2')
            with self.assertRaises(ValueError):
                isolated_consolidated_target(self.manga.parent,'2')
        self.assertIsNone(isolated_consolidated_target(self.manga,'2'))

    def test_real_consolidator_publishes_only_target_with_mocks_for_inputs(self):
        image=self.manga/'example_clean.png'
        image.write_bytes(b'test-image')
        manifest={'source_artifacts':['example.png'], 'clean_artifacts':['clean/example_clean.png']}
        with (numbered_consolidated_in_isolated_workspace(self.manga),
              patch.object(con,'_stage_manifest',return_value=manifest),
              patch.object(con,'_manifest_matches_merge',return_value=True),
              patch.object(con,'_stage_manifest_sha256',return_value='digest'),
              patch.object(con,'_valid_level2',return_value=(None,None,None)),
              patch.object(con,'_select_artifacts',return_value=[(image,con.LEVEL1)]),
              patch.object(con,'mirror_stage_chapter') as mirror):
            result=con.rebuild_consolidated(self.manga,'2')
        self.assertEqual(result['outputs'],1)
        target=self.manga/'FLUXO_SECUNDARIO/04_TEXTO_OFF/02_MAPEAR/INPUT_CONSOLIDADO/2/json/clean-manifest.json'
        self.assertTrue(target.is_file())
        self.assertFalse((self.manga/'FLUXO_SECUNDARIO/04_TEXTO_OFF/TO_MERGED_CONSOLIDADO/2').exists())
        mirror.assert_not_called()
