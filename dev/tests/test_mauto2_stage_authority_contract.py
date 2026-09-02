import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
PW=(ROOT/'interface_web'/'processing_web.py').read_text(encoding='utf-8')
APP=(ROOT/'interface_web'/'app.js').read_text(encoding='utf-8')
ST=(ROOT/'processamento'/'unificacao_imagens'/'image_stitcher.py').read_text(encoding='utf-8')
RV=(ROOT/'processamento'/'unificacao_imagens'/'image_stitcher_review.py').read_text(encoding='utf-8')

class Mauto2StageAuthorityContract(unittest.TestCase):
    def test_level1_supports_staged_output(self):
        self.assertIn('output_dir_override: Path | None = None', ST)
        self.assertIn('auto_merge_level1_complete', PW)
        self.assertIn('_promote_level1_complete(ch)', PW)

    def test_level2_does_not_duplicate_level1(self):
        body=PW.split('def validate_merge_level2(ch):',1)[1].split('\ndef catalog():',1)[0]
        self.assertIn('merge_level2_bounded_safe_path_v1', body)
        self.assertIn('solve_pending_region', body)
        self.assertIn('"level1_artifacts_duplicated":False', body)
        self.assertIn('"v3_thresholds_relaxed":False', body)
        self.assertNotIn('storage":"MERGE_LEVEL2"', body)

    def test_final_composition_includes_auto_merge(self):
        self.assertIn('_stage_artifact_pieces(auto_dir,auto,"artifacts","auto_merge")', PW)
        self.assertIn('"auto_merge_manifest":"auto-merge-manifest.json"', PW)
        self.assertIn('"kind":"auto_merge"', RV)
        self.assertIn('merge_auto_level2_level3_review_composition_v2', RV)

    def test_auto_merge_folder_button_uses_real_modal_actions(self):
        self.assertIn('document.querySelector("#appModal .app-modal-actions")', APP)
        self.assertIn('openBtn.textContent="Abrir pasta"', APP)

if __name__=='__main__': unittest.main()
