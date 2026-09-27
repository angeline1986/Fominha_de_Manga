import json
import unittest
from urllib.parse import urlencode

from dev.tests.auto_merge_query_fixtures import QueryFixtures
from central_v2.backend.routes.router import dispatch_get


class Level1QueryTests(QueryFixtures, unittest.TestCase):
    def query(self, **selection):
        params = {'provider': 'comix', 'manga': 'Obra Teste', **selection}
        return dispatch_get('/api/auto-merge/level1?' + urlencode(params), self.output)

    def test_read_only_query_isolated_per_chapter_and_naturally_sorted(self):
        self.chapter('10')
        self.chapter('2')
        directory, manifest = self.stage(chapter='2')
        manifest.write_text('{')
        self.attempt({'schema_version': 1, 'chapter': '1', 'message': 'Historical failure'})
        before = self.snapshot()
        response = self.query()
        self.assertEqual(response.status, 200)
        rows = json.loads(response.body)['chapters']
        self.assertEqual([row['chapter'] for row in rows], ['1', '2', '10'])
        self.assertEqual(rows[0]['level1']['status'], 'absent')
        self.assertEqual(rows[1]['level1']['status'], 'invalid')
        self.assertEqual(rows[0]['attempt']['message'], 'Historical failure')
        self.assertEqual(self.snapshot(), before)
        self.assertNotIn('merge_state', response.body.decode())
        self.assertNotIn(str(self.output), response.body.decode())

    def test_existing_partial_record_is_not_reinterpreted_from_attempt(self):
        self.stage(kind='partial', artifacts=[], pending_segments=[{'global_start': 0, 'global_end': 100}])
        self.attempt({'chapter': '1', 'message': 'Later stage', 'partition': {'pending_segments': []}})
        response = self.query()
        row = json.loads(response.body)['chapters'][0]
        self.assertEqual(row['level1']['residuals'], [{'global_start': 0, 'global_end': 100}])

    def test_invalid_or_outside_catalog_selection_is_rejected(self):
        for selection in (
            {'provider': 'unknown'}, {'manga': '../'}, {'manga': '.'},
            {'manga': 'missing'}, {'provider': ''}, {'manga': ''},
        ):
            with self.subTest(selection=selection):
                self.assertEqual(self.query(**selection).status, 400)

    def test_symlinked_chapter_outside_img_is_rejected(self):
        outside = self.output.parent / 'outside'
        outside.mkdir()
        (outside / 'page-001.png').write_bytes(b'outside')
        (self.manga / 'IMG' / 'bad').symlink_to(outside, target_is_directory=True)
        self.assertEqual(self.query().status, 400)

    def test_empty_work_returns_empty_list_without_creating_output(self):
        for source in (self.manga / 'IMG' / '1').iterdir():
            source.unlink()
        response = self.query()
        self.assertEqual(response.status, 200)
        self.assertEqual(json.loads(response.body)['chapters'], [])
        self.assertFalse((self.manga / 'FLUXO_SECUNDARIO').exists())


if __name__ == '__main__':
    unittest.main()
