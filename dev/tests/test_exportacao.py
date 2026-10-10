import tempfile, unittest
from pathlib import Path
from processamento.exportacao import exportador

class ExportacaoTest(unittest.TestCase):
 def setUp(self): exportador._PLANS.clear()
 def manga(self,root):
  m=root/"obra"; a=m/"FLUXO_SECUNDARIO"/"04_TEXTO_OFF"/"MERGED"/"1"; b=m/"FLUXO_SECUNDARIO"/"03_PDF_MERGE"/"1"; a.mkdir(parents=True); b.mkdir(parents=True)
  (a/"page-001.png").write_bytes(b"image"); (a/"page-001_mask.png").write_bytes(b"mask"); (a/"manifest.json").write_text("{}"); (a/".DS_Store").write_bytes(b"x"); (b/"1.pdf").write_bytes(b"pdf"); return m
 def test_exclusions(self):
  with tempfile.TemporaryDirectory() as td:
   r=Path(td); m=self.manga(r); d=r/"dest"; d.mkdir(); plan=exportador.simulate_export(m,str(d),["textoff_merged","pdf_merge"]); self.assertEqual(plan["total_files"],2)
 def test_preserves_extra_and_structure(self):
  with tempfile.TemporaryDirectory() as td:
   r=Path(td); m=self.manga(r); d=r/"dest"; d.mkdir(); (d/"keep.txt").write_text("keep"); plan=exportador.simulate_export(m,str(d),["textoff_merged","pdf_merge"]); out=exportador.execute_plan(m,plan["plan_id"]); self.assertTrue((d/"keep.txt").is_file()); self.assertTrue((d/"obra"/"raws_semi-clean"/"1"/"page-001.png").is_file()); self.assertTrue((d/"obra"/"Traducoes"/"1"/"1.pdf").is_file()); self.assertEqual(out["copied"],2)
 def test_source_change_invalidates(self):
  with tempfile.TemporaryDirectory() as td:
   r=Path(td); m=self.manga(r); d=r/"dest"; d.mkdir(); plan=exportador.simulate_export(m,str(d),["textoff_merged"]); (m/"FLUXO_SECUNDARIO"/"04_TEXTO_OFF"/"MERGED"/"1"/"page-001.png").write_bytes(b"changed")
   with self.assertRaisesRegex(ValueError,"mudou desde a simulação"): exportador.execute_plan(m,plan["plan_id"])
 def test_appledouble_excluded_in_simulation_and_execution(self):
  with tempfile.TemporaryDirectory() as td:
   r=Path(td); m=self.manga(r); d=r/"dest"; d.mkdir()
   pdf_dir=m/"FLUXO_SECUNDARIO"/"03_PDF_MERGE"/"1"
   merged_dir=m/"FLUXO_SECUNDARIO"/"04_TEXTO_OFF"/"MERGED"/"1"
   for name in ("._1.pdf","._1","._.DS_Store"):
    (pdf_dir/name).write_bytes(b"macos-metadata")
   (merged_dir/"._page-001.png").write_bytes(b"macos-metadata")
   plan=exportador.simulate_export(m,str(d),["pdf_merge","textoff_merged"])
   self.assertEqual(plan["total_files"],2)
   self.assertEqual(plan["new_files"],2)
   self.assertIn("._*",plan["exclusions"])
   out=exportador.execute_plan(m,plan["plan_id"])
   self.assertEqual(out["copied"],2)
   self.assertTrue((d/"obra"/"Traducoes"/"1"/"1.pdf").is_file())
   self.assertTrue((d/"obra"/"raws_semi-clean"/"1"/"page-001.png").is_file())
   self.assertFalse(any(p.name.startswith("._") for p in (d/"obra").rglob("*")))

if __name__=="__main__": unittest.main()
