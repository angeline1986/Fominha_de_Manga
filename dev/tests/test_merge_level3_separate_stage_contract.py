import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACK = (ROOT / "interface_web" / "processing_web.py").read_text(encoding="utf-8")
APP = (ROOT / "interface_web" / "app.js").read_text(encoding="utf-8")
INDEX = (ROOT / "interface_web" / "index.html").read_text(encoding="utf-8")

class MergeLevel3SeparateStageContractTests(unittest.TestCase):
    def test_level2_stops_after_level2_validation(self):
        block = BACK.split("def do_merge_level2(job,chs):",1)[1].split("def do_merge_level3(job,chs):",1)[0]
        self.assertNotIn("process_merge_level3_pending", block)
        self.assertNotIn("_promote_level3_complete", block)
        self.assertIn("validate_merge_level2(ch)", block)

    def test_level3_is_explicit_backend_job(self):
        self.assertIn('elif job.action=="merge_level3": job.result=do_merge_level3(job,chs)', BACK)
        block = BACK.split("def do_merge_level3(job,chs):",1)[1].split("def do_pdf(job,chs):",1)[0]
        self.assertIn("process_merge_level3_pending(ch,part)", block)
        self.assertIn("_promote_level3_complete(ch,part)", block)
        self.assertIn("_is_level2_validated(failure)", block)

    def test_state_machine_has_pending_level3(self):
        self.assertIn('"merge_level3_pending":level3_pending', BACK)
        self.assertIn('"pendente_level3"', BACK)
        self.assertIn("level3_has_residual", BACK)
        self.assertIn('"level3_pending":sum(', BACK)

    def test_frontend_executes_level3_explicitly(self):
        self.assertIn("runSelected('merge_level3')", APP)
        self.assertIn("Analisar Nível III", APP)
        self.assertIn("x.merge_level3_pending||x.merge_level3_detail?.available", APP)
        self.assertIn('id="badgeLevel3"', INDEX)

    def test_review_is_blocked_until_level3_exists(self):
        self.assertIn("Auto-Merge Nível III ainda não foi validado", BACK)
        self.assertIn('"level3_pending"', BACK)

if __name__=="__main__":
    unittest.main()
