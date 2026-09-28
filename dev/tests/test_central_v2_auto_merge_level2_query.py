import json
import unittest
from urllib.parse import urlencode

from PIL import Image

from dev.tests.auto_merge_query_fixtures import QueryFixtures
from central_v2.backend.routes.router import dispatch_get


class Level2ResidualQueryTests(QueryFixtures, unittest.TestCase):
    def test_residual_regions_use_merge_output_page_names_without_internal_suffixes(self):
        chapter = self.manga / 'IMG' / '1'
        (chapter / 'page-001.png').unlink()
        Image.new('RGB', (8, 10)).save(chapter / 'page-155.png')
        Image.new('RGB', (8, 20)).save(chapter / 'page-160.png')
        stage, _ = self.stage(
            kind='partial', total_height=30,
            artifacts=[{'file': 'page-001.png', 'global_start': 0, 'global_end': 30}],
            pending_segments=[{'global_start': 5, 'global_end': 25}],
        )
        Image.new('RGB', (8, 5)).save(stage / 'page-001.png')

        rows = json.loads(self.query().body)['chapters']

        self.assertEqual(rows[0]['residual_regions'], ['page-155-160.png'])

    def query(self):
        params = urlencode({'provider': 'comix', 'manga': 'Obra Teste'})
        return dispatch_get('/api/auto-merge/level2?' + params, self.output)

    def test_only_valid_level1_residuals_are_returned_with_interval_data(self):
        stage, _ = self.stage(
            kind='partial',
            total_height=300,
            pending_segments=[
                {'global_start': 120, 'global_end': 180},
                {'global_start': 240, 'global_end': 300},
            ],
        )
        (stage / 'page-001.png').write_bytes(b'stage artifact')
        self.chapter('2')
        self.stage(chapter='2', kind='complete')
        before = self.snapshot()

        response = self.query()

        self.assertEqual(response.status, 200)
        payload = json.loads(response.body)
        self.assertEqual(payload['provider'], 'comix')
        self.assertEqual(payload['manga'], 'Obra Teste')
        self.assertEqual(len(payload['chapters']), 1)
        row = payload['chapters'][0]
        self.assertEqual(row['chapter'], '1')
        self.assertEqual(row['residual_segments'], 2)
        self.assertEqual(row['residual_height'], 120)
        self.assertEqual(row['residuals'], [
            {'global_start': 120, 'global_end': 180},
            {'global_start': 240, 'global_end': 300},
        ])
        self.assertEqual(row['level1_artifacts'], 1)
        self.assertEqual(self.snapshot(), before)

    def test_partial_record_with_missing_level1_artifact_is_not_eligible(self):
        self.stage(
            kind='partial',
            total_height=180,
            pending_segments=[{'global_start': 120, 'global_end': 180}],
        )
        rows = json.loads(self.query().body)['chapters']
        self.assertEqual(rows, [])

    def test_official_merge_excludes_chapter_from_level2_residual_table(self):
        stage, _ = self.stage(
            kind='partial',
            total_height=180,
            pending_segments=[{'global_start': 120, 'global_end': 180}],
        )
        (stage / 'page-001.png').write_bytes(b'stage artifact')
        official = self.manga / 'FLUXO_SECUNDARIO' / '02_MERGE' / '1'
        official.mkdir(parents=True)
        (official / 'merge-manifest.json').write_text(
            json.dumps({'algorithm': 'test', 'outputs': []}), encoding='utf-8',
        )
        rows = json.loads(self.query().body)['chapters']
        self.assertEqual(rows, [])

    def test_existing_level2_stage_is_not_offered_for_reexecution(self):
        stage, _ = self.stage(
            kind='partial', total_height=180,
            pending_segments=[{'global_start': 120, 'global_end': 180}],
        )
        (stage / 'page-001.png').write_bytes(b'stage artifact')
        level2 = self.manga / 'FLUXO_SECUNDARIO' / '01_MERGE_PROCESSAMENTO' / 'MERGE_LEVEL2' / '1'
        level2.mkdir(parents=True)
        (level2 / 'keep.txt').write_text('existing stage')
        rows = json.loads(self.query().body)['chapters']
        self.assertEqual(rows, [])
        self.assertEqual((level2 / 'keep.txt').read_text(), 'existing stage')


if __name__ == '__main__':
    unittest.main()
