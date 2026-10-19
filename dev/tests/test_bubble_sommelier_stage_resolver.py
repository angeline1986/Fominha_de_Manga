"""Bubble Sommelier must use the registered read authority for paths."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from central_v2.backend.orchestration.bubble_sommelier import artifacts
from central_v2.backend.orchestration.textoff_merged import artifact_migration


class BubbleSommelierStageResolverTests(unittest.TestCase):
    def test_execution_paths_follow_registry_authority(self):
        for authority, folder in (
            ('legacy', 'BUBBLE_SOMMELIER'),
            ('target', '03_BUBBLE_SOMMELIER'),
        ):
            with self.subTest(authority=authority), TemporaryDirectory() as td:
                manga = Path(td) / 'manga'
                registry = json.loads(artifact_migration.REGISTRY_PATH.read_text())
                registry['read_authority'] = authority
                for entry in registry['stages']:
                    if entry.get('dual_write'):
                        entry['read_authority'] = authority
                config = Path(td) / 'registry.json'
                config.write_text(json.dumps(registry))
                with patch.object(artifact_migration, 'REGISTRY_PATH', config):
                    expected = manga / 'FLUXO_SECUNDARIO/04_TEXTO_OFF' / folder / '1'
                    if authority == 'target':
                        expected.mkdir(parents=True)
                    self.assertEqual(artifacts.execution_dir(manga, '1'), expected)
                    self.assertEqual(artifacts.report_path(manga, '1'), expected / 'report.json')
                    self.assertEqual(artifacts.crops_dir(manga, '1'), expected / 'crops')

    def test_target_missing_does_not_fallback_to_legacy(self):
        with TemporaryDirectory() as td:
            manga = Path(td) / 'manga'
            legacy = manga / 'FLUXO_SECUNDARIO/04_TEXTO_OFF/BUBBLE_SOMMELIER/1'
            legacy.mkdir(parents=True)
            registry = json.loads(artifact_migration.REGISTRY_PATH.read_text())
            registry['read_authority'] = 'target'
            for entry in registry['stages']:
                if entry.get('dual_write'):
                    entry['read_authority'] = 'target'
            config = Path(td) / 'registry.json'
            config.write_text(json.dumps(registry))
            with patch.object(artifact_migration, 'REGISTRY_PATH', config):
                with self.assertRaises(artifact_migration.ArtifactAuthorityUnavailable):
                    artifacts.execution_dir(manga, '1')


if __name__ == '__main__':
    unittest.main()
