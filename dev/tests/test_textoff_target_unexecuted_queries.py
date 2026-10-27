"""Etapas nunca executadas vs. espelho obrigatório ausente sob target."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from central_v2.backend.orchestration.textoff_merged import artifact_migration
from central_v2.backend.orchestration.textoff_merged.consolidated import consolidated_is_current
from central_v2.backend.orchestration.textoff_merged.level3_query import _chapter_row
from central_v2.backend.orchestration.bubble_sommelier.query import query as sommelier_query


class TargetUnexecutedQueriesTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.manga = Path(temporary.name) / 'manga'
        self.manga.mkdir()
        registry = json.loads(artifact_migration.REGISTRY_PATH.read_text(encoding='utf-8'))
        registry['migration_mode'] = 'dual_write'
        registry['dual_write_enabled'] = True
        registry['read_authority'] = 'target'
        for entry in registry['stages']:
            if entry.get('classification') in {'PERSISTENT_STAGE', 'CONSOLIDATED_OUTPUT_INTERMEDIATE'}:
                entry['dual_write'] = True
                entry['read_authority'] = 'target'
        self.registry = Path(temporary.name) / 'registry.json'
        self.registry.write_text(json.dumps(registry), encoding='utf-8')
        context = patch.object(artifact_migration, 'REGISTRY_PATH', self.registry)
        context.start()
        self.addCleanup(context.stop)
        self.off = self.manga / 'FLUXO_SECUNDARIO/04_TEXTO_OFF'

    def test_consolidated_unexecuted_returns_false(self):
        self.assertFalse(consolidated_is_current(self.manga, '2'))

    def test_consolidated_lost_target_still_raises(self):
        (self.off / 'TO_MERGED_CONSOLIDADO/2').mkdir(parents=True)
        with patch.object(artifact_migration, 'emit'):
            with self.assertRaises(artifact_migration.ArtifactAuthorityUnavailable):
                consolidated_is_current(self.manga, '2')

    def test_mapear_unexecuted_is_pending(self):
        with patch('central_v2.backend.orchestration.textoff_merged.level3_query.consolidated_is_current', return_value=False), \
             patch('central_v2.backend.orchestration.textoff_merged.level3_query._manifest_matches_merge', return_value=True), \
             patch('central_v2.backend.orchestration.textoff_merged.level3_query._stage_manifest', return_value={}), \
             patch('central_v2.backend.orchestration.textoff_merged.level3_query.observe_shadow_read'):
            row = _chapter_row(self.manga, '2', {'2': {'merge_valid': True, 'merge_count': 1}})
        self.assertEqual(row['level3_status'], 'missing_level1')

    def test_mapear_lost_target_still_raises(self):
        (self.off / 'TO_MERGED_NIVEL_III/2').mkdir(parents=True)
        with patch('central_v2.backend.orchestration.textoff_merged.level3_query.consolidated_is_current', return_value=False), \
             patch('central_v2.backend.orchestration.textoff_merged.level3_query._manifest_matches_merge', return_value=True), \
             patch('central_v2.backend.orchestration.textoff_merged.level3_query._stage_manifest', return_value={}), \
             patch.object(artifact_migration, 'emit'):
            with self.assertRaises(artifact_migration.ArtifactAuthorityUnavailable):
                _chapter_row(self.manga, '2', {})

    def test_sommelier_unexecuted_returns_none(self):
        (self.manga / 'FLUXO_SECUNDARIO/02_MERGE/2').mkdir(parents=True)
        with patch('central_v2.backend.orchestration.bubble_sommelier.query.images', return_value=[Path('page.png')]), \
             patch('central_v2.backend.orchestration.bubble_sommelier.query.observe_shadow_read'):
            rows = sommelier_query(self.manga)['chapters']
        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0]['sommelier'])

    def test_sommelier_lost_target_still_raises(self):
        (self.manga / 'FLUXO_SECUNDARIO/02_MERGE/2').mkdir(parents=True)
        (self.off / 'BUBBLE_SOMMELIER/2').mkdir(parents=True)
        with patch('central_v2.backend.orchestration.bubble_sommelier.query.images', return_value=[]), \
             patch.object(artifact_migration, 'emit'):
            with self.assertRaises(artifact_migration.ArtifactAuthorityUnavailable):
                sommelier_query(self.manga)


if __name__ == '__main__':
    unittest.main()
