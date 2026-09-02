import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = (ROOT / "interface_web" / "app.js").read_text(encoding="utf-8")
INDEX = (ROOT / "interface_web" / "index.html").read_text(encoding="utf-8")
CSS = (ROOT / "interface_web" / "styles.css").read_text(encoding="utf-8")


class MergeLevel3UiPageContractTests(unittest.TestCase):
    def test_level3_has_own_navigation_and_render_target(self):
        self.assertIn('data-page="merge_level3"', INDEX)
        self.assertIn('if(page==="merge_level3")return mergeLevel3(root);', APP)
        self.assertIn('function mergeLevel3(r)', APP)

    def test_level3_page_reads_persisted_detail_only(self):
        self.assertIn('merge_level3_detail?.available', APP)
        self.assertIn('residual_pending_segments||[]', APP)
        self.assertIn('safe_artifacts||[]', APP)
        self.assertIn('diagnostics||[]', APP)

    def test_level3_page_is_operational_and_can_route_to_review_v2(self):
        level3_block = APP.split('function mergeLevel3(r)', 1)[1].split('function chosen(){', 1)[0]
        self.assertNotIn("job('merge_level3'", level3_block)
        self.assertNotIn("reviewDecision('approve'", level3_block)
        self.assertIn("page='review_v2'", level3_block)

    def test_level3_uses_isolated_css_namespace(self):
        self.assertIn('.l3-table', CSS)
        self.assertIn('.l3-detail-panel', CSS)
        self.assertIn('.l3-inline-diag', CSS)


if __name__ == "__main__":
    unittest.main()
