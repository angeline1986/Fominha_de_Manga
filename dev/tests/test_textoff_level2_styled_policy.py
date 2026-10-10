"""M2 regression: the Check classification must survive Level II masking."""
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from central_v2.backend.orchestration.textoff_merged.level2_manual_protection import (
    load_level1_protection, protect_level2_masks,
)
from central_v2.backend.orchestration.textoff_merged.occurrence_policy import (
    protected_types_for_transparency_basic,
)


class StyledPolicyIntegrationTests(unittest.TestCase):
    def test_saved_styled_occurrence_is_loaded_and_protects_pixels(self):
        with tempfile.TemporaryDirectory() as temp:
            manga = Path(temp) / 'comix' / 'obra'
            check = manga / ('FLUXO_SECUNDARIO/04_TEXTO_OFF/'
                             '04_AUTO_CLEANER_CHECK/1/auto-cleaner-check-manifest.json')
            check.parent.mkdir(parents=True)
            rows = [
                {'id': 'styled', 'page': 'page.png', 'tipo': 'balao_estilizado',
                 'box_normalized': {'left': .25, 'top': .25, 'width': .5, 'height': .5}},
                {'id': 'text', 'page': 'page.png', 'tipo': 'texto_residual',
                 'box_normalized': {'left': 0, 'top': 0, 'width': .2, 'height': .2}},
            ]
            check.write_text(json.dumps({
                'schema': 'textoff_auto_cleaner_check_manifest_v1', 'version': 1,
                'provider': 'comix', 'manga': 'obra', 'chapter': '1',
                'source_snapshot': {}, 'approved_occurrences': rows,
            }), encoding='utf-8')
            selected=load_level1_protection(manga,'comix','obra','1')
            self.assertEqual([x['id'] for x in selected['page.png']], ['styled'])
            automatic=np.full((20,20),255,dtype=np.uint8)
            masks, summary=protect_level2_masks([automatic],selected['page.png'],automatic.shape)
            self.assertEqual(summary['protected_occurrences'],1)
            self.assertEqual(summary['protected_types'],['balao_estilizado'])
            self.assertEqual(summary['protected_pixels'],100)
            self.assertEqual(int(np.count_nonzero(masks[0][5:15,5:15])),0)
            self.assertEqual(int(np.count_nonzero(masks[0])),300)

    def test_all_policy_protected_types_are_excluded(self):
        mask=np.full((20,20),255,dtype=np.uint8)
        box={'left': .25, 'top': .25, 'width': .5, 'height': .5}
        for kind in sorted(protected_types_for_transparency_basic()):
            with self.subTest(kind=kind):
                masks,summary=protect_level2_masks([mask],[{'tipo':kind,'box_normalized':box}],mask.shape)
                self.assertEqual(summary['protected_occurrences'],1)
                self.assertEqual(summary['protected_pixels'],100)
                self.assertEqual(int(np.count_nonzero(masks[0][5:15,5:15])),0)

    def test_unprotected_types_remain_eligible(self):
        mask=np.full((20,20),255,dtype=np.uint8)
        box={'left': .25, 'top': .25, 'width': .5, 'height': .5}
        for kind in ('texto_residual','residuo_transparencia'):
            with self.subTest(kind=kind):
                masks, summary=protect_level2_masks([mask],[{'tipo':kind,'box_normalized':box}],mask.shape)
                self.assertEqual(summary['protected_occurrences'],0)
                np.testing.assert_array_equal(masks[0],mask)


if __name__ == '__main__':
    unittest.main()
