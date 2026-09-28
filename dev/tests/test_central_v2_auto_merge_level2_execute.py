import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from orquestracao.auto_merge.executar_nivel2 import execute_level2
from central_v2.backend.routes.router import dispatch_post
from processamento.unificacao_imagens import image_stitcher as v3


class Level2ExecutionTests(unittest.TestCase):
    def test_execution_endpoint_is_registered_and_validates_payload(self):
        with tempfile.TemporaryDirectory() as temporary:
            response = dispatch_post(
                '/api/auto-merge/level2/execute', {}, Path(temporary),
            )
        self.assertEqual(response.status, 400)

    def make_chapter(self, root, with_safe_band):
        manga = Path(root) / 'comix' / 'Synthetic'
        chapter = manga / 'IMG' / '1'
        chapter.mkdir(parents=True)
        Image.new('RGB', (32, 100), (40, 80, 120)).save(chapter / 'page-001.png')
        rows = np.zeros((14000, 32, 3), dtype=np.uint8)
        if with_safe_band:
            rows[6900:7200] = 255
        else:
            rows[::2] = 10
            rows[1::2] = 40
        Image.fromarray(rows).save(chapter / 'page-002.png')

        level1_dir = manga / 'FLUXO_SECUNDARIO' / '01_MERGE_PROCESSAMENTO' / 'AUTO_MERGE' / '1'
        level1_dir.mkdir(parents=True)
        Image.new('RGB', (32, 100), (40, 80, 120)).save(level1_dir / 'auto-001.png')
        manifest = {
            'schema_version': 1,
            'algorithm': 'auto_merge_level1_resolved_segments',
            'chapter': '1',
            'total_height': 14100,
            'artifacts': [{'file': 'auto-001.png', 'global_start': 0, 'global_end': 100}],
            'pending_segments': [{'global_start': 100, 'global_end': 14100}],
        }
        manifest_path = level1_dir / 'auto-merge-manifest.json'
        manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
        return manga, chapter, manifest_path

    def run_level2(self, manga):
        progress = []
        result = execute_level2(
            manga, ['1'], 'test-job',
            lambda chapter, event: progress.append(event),
        )
        self.assertEqual(progress[-1]['percent'], 100)
        return result[0]

    def test_unresolved_residual_is_preserved_without_touching_level1_or_sources(self):
        with tempfile.TemporaryDirectory() as temporary:
            manga, chapter, manifest_path = self.make_chapter(temporary, False)
            source_hashes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                             for path in chapter.iterdir()}
            manifest_hash = hashlib.sha256(manifest_path.read_bytes()).hexdigest()

            result = self.run_level2(manga)

            self.assertEqual(result['status'], 'partial')
            self.assertEqual(result['pending_segments'], 1)
            self.assertEqual(result['next_stage'], 'Auto-Merge Nível III')
            stage = manga / 'FLUXO_SECUNDARIO' / '01_MERGE_PROCESSAMENTO' / 'MERGE_LEVEL2' / '1'
            level2 = json.loads((stage / 'merge-level2-manifest.json').read_text())
            self.assertEqual(level2['source_level1_sha256'], manifest_hash)
            self.assertEqual(len(level2['pending_segments']), 1)
            self.assertEqual(level2['artifacts'], [])
            self.assertEqual(hashlib.sha256(manifest_path.read_bytes()).hexdigest(), manifest_hash)
            self.assertEqual(source_hashes, {
                path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in chapter.iterdir()
            })
            self.assertFalse(v3.is_chapter_merged(chapter))

    def test_complete_residual_promotes_level1_plus_level2_without_rerendering(self):
        with tempfile.TemporaryDirectory() as temporary:
            manga, chapter, _ = self.make_chapter(temporary, True)
            result = self.run_level2(manga)

            self.assertEqual(result['status'], 'promoted')
            self.assertEqual(result['pending_segments'], 0)
            self.assertTrue(v3.is_chapter_merged(chapter))
            official = v3.merge_output_dir(chapter)
            manifest = json.loads((official / 'merge-manifest.json').read_text())
            self.assertEqual(manifest['algorithm'], 'merge_auto_level2_composition_v2')
            self.assertEqual([item['source_stage'] for item in manifest['outputs']],
                             ['auto_merge', 'level2', 'level2'])


if __name__ == '__main__':
    unittest.main()
