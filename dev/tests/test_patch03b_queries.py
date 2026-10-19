"""Patch 03B tests: absence is pending; missing mirror still fails closed."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from central_v2.backend.orchestration.textoff_merged import artifact_migration
from central_v2.backend.orchestration.textoff_merged.level3_query import _chapter_row
from central_v2.backend.orchestration.textoff_merged.unexecuted_stage import both_absent
from central_v2.backend.orchestration.bubble_sommelier.query import query


class MissingStageQueries(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.manga = Path(self.tmp.name)

    def make(self, path):
        full = self.manga / 'FLUXO_SECUNDARIO/04_TEXTO_OFF' / path
        full.mkdir(parents=True, exist_ok=True)
        return full

    def test_both_absent(self):
        self.assertTrue(both_absent(self.manga, 'TO_MERGED_NIVEL_I', '01_AUTO_CLEANER', '2'))
        self.make('TO_MERGED_NIVEL_I/2')
        self.assertFalse(both_absent(self.manga, 'TO_MERGED_NIVEL_I', '01_AUTO_CLEANER', '2'))

    def test_mapear_missing_entire_pipeline(self):
        row = _chapter_row(self.manga, '2', {'2': {'merge_valid': True, 'merge_count': 15}})
        self.assertEqual(row['level3_status'], 'missing_level1')
        self.assertFalse(row['cleaned'])
        self.assertEqual(row['merge_count'], 15)

    def test_legacy_level1_does_not_bypass_resolver(self):
        self.make('TO_MERGED_NIVEL_I/2')
        with patch('central_v2.backend.orchestration.textoff_merged.level3_query.consolidated_is_current', return_value=False), \
             patch('central_v2.backend.orchestration.textoff_merged.level3_query._stage_manifest', side_effect=artifact_migration.ArtifactAuthorityUnavailable('MISSING_TARGET')):
            with self.assertRaises(artifact_migration.ArtifactAuthorityUnavailable):
                _chapter_row(self.manga, '2', {})

    def test_sommelier_pending(self):
        merge = self.manga / 'FLUXO_SECUNDARIO/02_MERGE/2'
        merge.mkdir(parents=True)
        with patch('central_v2.backend.orchestration.bubble_sommelier.query.images', return_value=[]), \
             patch('central_v2.backend.orchestration.bubble_sommelier.query.stage_chapter', side_effect=AssertionError('should not resolve')):
            result = query(self.manga)
        self.assertIsNone(result['chapters'][0]['sommelier'])

    def test_sommelier_existing_legacy_resolves_and_propagates(self):
        merge = self.manga / 'FLUXO_SECUNDARIO/02_MERGE/2'
        merge.mkdir(parents=True)
        self.make('BUBBLE_SOMMELIER/2')
        with patch('central_v2.backend.orchestration.bubble_sommelier.query.images', return_value=[]), \
             patch('central_v2.backend.orchestration.bubble_sommelier.query.stage_chapter', side_effect=artifact_migration.ArtifactAuthorityUnavailable('MISSING_TARGET')):
            with self.assertRaises(artifact_migration.ArtifactAuthorityUnavailable):
                query(self.manga)


if __name__ == '__main__':
    unittest.main()
