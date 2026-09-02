import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = (ROOT / "interface_web" / "app.js").read_text(encoding="utf-8")
CSS = (ROOT / "interface_web" / "styles.css").read_text(encoding="utf-8")

class MergeLevel3UiAlignmentContractTests(unittest.TestCase):
    def test_level3_uses_level2_operational_structure(self):
        block = APP.split("function mergeLevel3(r){",1)[1].split("function toggleLevel3Detail",1)[0]
        self.assertIn('head("Auto-Merge Nível III"', block)
        self.assertIn('class="toolbar"', block)
        self.assertIn('class="panel"', block)
        self.assertIn('class="l3-table"', block)
        self.assertIn('table-pager', block)

    def test_level3_explains_explicit_execution(self):
        block = APP.split("function mergeLevel3(r){",1)[1].split("function toggleLevel3Detail",1)[0]
        self.assertIn("Analisar Nível III", block)
        self.assertIn("runSelected(\'merge_level3\')", block)

    def test_diagnostics_are_secondary_detail(self):
        self.assertIn("function toggleLevel3Detail(ch)", APP)
        self.assertIn("function level3DetailPanel(x)", APP)
        self.assertIn("l3-detail-row", APP)
        self.assertIn(".l3-detail-panel", CSS)

    def test_review_v2_route_preserved(self):
        self.assertIn("page='review_v2'", APP)

if __name__ == "__main__":
    unittest.main()
