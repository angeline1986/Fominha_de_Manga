from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]

class MergeReviewV2UiContractTests(unittest.TestCase):
    def test_review_v2_is_separate_navigation_and_render_target(self):
        html=(ROOT/"interface_web/index.html").read_text(encoding="utf-8")
        js=(ROOT/"interface_web/app.js").read_text(encoding="utf-8")
        self.assertIn('data-page="review_v2"',html)
        self.assertIn('if(page==="review_v2")return reviewV2(root)',js)
        self.assertIn('function reviewV2(r)',js)

    def test_review_v2_uses_valid_level3_residual_and_existing_review_actions(self):
        js=(ROOT/"interface_web/app.js").read_text(encoding="utf-8")
        self.assertIn('x.merge_level3_detail?.available',js)
        self.assertIn('x.merge_level3_detail?.valid',js)
        self.assertIn('d.review_pending_segments||d.residual_pending_segments',js)
        self.assertIn('reviewDecision(\'review\'',js)
        self.assertIn('reviewDecision(\'approve\'',js)
        self.assertIn('reviewDecision(\'reject\'',js)

    def test_review_v2_has_isolated_css_namespace(self):
        css=(ROOT/"interface_web/styles.css").read_text(encoding="utf-8")
        self.assertIn('/* MIII-4D REVIEW MERGE V2 */',css)
        self.assertIn('.rv2-flow',css)
        self.assertIn('.rv2-compare',css)
        self.assertIn('.rv2-diagnosis',css)

if __name__=="__main__": unittest.main()
