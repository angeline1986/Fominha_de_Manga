import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PW = (ROOT / "interface_web" / "processing_web.py").read_text(encoding="utf-8")
APP = (ROOT / "interface_web" / "app.js").read_text(encoding="utf-8")

class MergeLevel1AutoMergePersistenceContractTests(unittest.TestCase):
    def test_level1_has_dedicated_storage(self):
        self.assertIn('def amdir(m,c): return m/"FLUXO_SECUNDARIO"/"AUTO_MERGE"/c', PW)
        self.assertIn('"algorithm": "auto_merge_level1_resolved_segments"', PW)
        self.assertIn('"storage":"AUTO_MERGE"', PW.replace(" ", ""))

    def test_level1_failure_materializes_resolved_segments(self):
        self.assertIn("artifacts=_materialize_level1_resolved(ch,part)", PW)
        self.assertIn('"auto_merge_saved":saved', PW)
        self.assertIn('"status":"partial" if saved else "error"', PW)

    def test_open_folder_supports_auto_merge(self):
        self.assertIn('"auto_merge":"AUTO_MERGE"', PW.replace(" ", ""))
        self.assertIn("kind=auto_merge", APP)
        self.assertIn("openAutoMergeFolder", APP)

    def test_ui_explains_saved_level1_work(self):
        self.assertIn("Auto-Merge concluído parcialmente", APP)
        self.assertIn("Os trechos resolvidos pelo Auto-Merge foram salvos.", APP)
        self.assertIn("merge(s) seguro(s) foram gerados e salvos em AUTO_MERGE", APP)
        self.assertIn("openAutoMergeFolder(savedItems[0].chapter)", APP)

if __name__ == "__main__":
    unittest.main()
