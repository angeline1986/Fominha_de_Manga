import json
import unittest

from dev.tests.auto_merge_query_fixtures import QueryFixtures
from processamento.unificacao_imagens.auto_merge.nivel1 import read_level1, read_official


class Level1ReaderTests(QueryFixtures, unittest.TestCase):
    def test_complete_record_lists_files_without_decoding_images(self):
        directory, _ = self.stage()
        (directory / 'page-001.png').write_bytes(b'no pixels decoded')
        result = read_level1(self.manga, '1')
        self.assertEqual(result.status, 'recorded')
        self.assertEqual(result.data['kind'], 'complete')
        self.assertTrue(result.data['artifacts'][0]['exists'])

    def test_partial_record_can_have_only_residuals(self):
        self.stage(kind='partial', artifacts=[], pending_segments=[{'global_start': 0, 'global_end': 100}])
        result = read_level1(self.manga, '1')
        self.assertEqual(result.status, 'recorded')
        self.assertEqual(result.data['artifacts'], [])
        self.assertEqual(result.data['residuals'], [{'global_start': 0, 'global_end': 100}])

    def test_absent_corrupt_and_unsupported_records_are_distinct(self):
        self.assertEqual(read_level1(self.manga, '1').status, 'absent')
        _, manifest = self.stage()
        manifest.write_text('{')
        self.assertEqual(read_level1(self.manga, '1').status, 'invalid')
        for changes in ({'schema_version': 9}, {'algorithm': []}, {'algorithm': 'unknown'}):
            self.stage(**changes)
            self.assertEqual(read_level1(self.manga, '1').status, 'unsupported')

    def test_invalid_shapes_are_reported_without_crashing_the_query(self):
        for changes in (
            {'chapter': 'another'}, {'total_height': True}, {'total_height': -1},
            {'artifacts': {}}, {'artifacts': [None]}, {'pending_segments': ['bad']},
            {'artifacts': [{'file': 'x.png', 'global_start': 0, 'global_end': 101}]},
            {'pending_segments': [{'global_start': 0, 'global_end': 100}]},
        ):
            with self.subTest(changes=changes):
                _, manifest = self.stage()
                payload = json.loads(manifest.read_text())
                payload.update(changes)
                manifest.write_text(json.dumps(payload))
                self.assertEqual(read_level1(self.manga, '1').status, 'invalid')

    def test_missing_and_external_artifacts_are_not_reported_as_present(self):
        directory, _ = self.stage()
        result = read_level1(self.manga, '1')
        self.assertFalse(result.data['artifacts'][0]['exists'])
        (directory / 'page-001.png').symlink_to(self.manga / 'IMG' / '1' / 'page-001.png')
        self.assertFalse(read_level1(self.manga, '1').data['artifacts'][0]['exists'])
        self.stage(artifacts=[{'file': '../page.png', 'global_start': 0, 'global_end': 100}])
        self.assertEqual(read_level1(self.manga, '1').status, 'invalid')

    def test_manifest_symlink_cannot_escape_the_work(self):
        _, manifest = self.stage()
        other = self.output.parent / 'outside.json'
        other.write_text(json.dumps({'secret': 'outside'}))
        manifest.unlink()
        manifest.symlink_to(other)
        record = read_level1(self.manga, '1')
        self.assertEqual(record.status, 'invalid')
        self.assertIsNone(record.data)

    def test_official_document_presence_is_not_a_physical_validation(self):
        path = self.manga / 'FLUXO_SECUNDARIO' / '02_MERGE' / '1' / 'merge-manifest.json'
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({'algorithm': 'later_stage', 'outputs': [{'file': 'missing.png'}]}))
        result = read_official(self.manga, '1')
        self.assertEqual(result.status, 'recorded')
        self.assertEqual(result.data['outputs_count'], 1)
        self.assertNotIn('validated', result.data)
        self.assertNotIn('merge_state', result.data)


if __name__ == '__main__':
    unittest.main()
