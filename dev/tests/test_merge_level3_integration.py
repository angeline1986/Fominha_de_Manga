import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from interface_web import processing_web as pw
from processamento.unificacao_imagens.image_stitcher_level3 import Level3Decision, Level3Result

class Level3PipelineIntegrationTests(unittest.TestCase):
    def make_case(self,root,height=13050):
        manga=Path(root)/"manga"; ch=manga/"IMG"/"6"; ch.mkdir(parents=True)
        Image.new("RGB",(32,height),"white").save(ch/"page-001.png")
        seg={"id":1,"status":"failed","validation":"review_required",
             "global_start":0,"global_end":height,"height":height,
             "sources":["page-001.png"],
             "source_spans":[{"file":"page-001.png","global_start":0,
             "global_end":height,"source_y_start":0,"source_y_end":height}]}
        part={"level2_validated":True,"total_height":height,
              "pending_segments":[seg],"resolved_segments":[]}
        return manga,ch,part

    def test_requires_validated_level2(self):
        with tempfile.TemporaryDirectory() as td:
            _,ch,part=self.make_case(td); part["level2_validated"]=False
            ok,_,manifest=pw.process_merge_level3_pending(ch,part)
            self.assertFalse(ok); self.assertIsNone(manifest)

    def test_inconclusive_is_residual(self):
        with tempfile.TemporaryDirectory() as td:
            _,ch,part=self.make_case(td)
            r=Level3Result(Level3Decision.INCONCLUSIVE,12000,
                "structural_evidence_inconclusive",0,13050,{},None)
            with patch("processamento.unificacao_imagens.image_stitcher_level3.search_local_safe_candidate",return_value=r):
                ok,_,m=pw.process_merge_level3_pending(ch,part)
            self.assertTrue(ok); self.assertEqual(m["safe_artifacts"],[])
            self.assertEqual(len(m["residual_pending_segments"]),1)
            self.assertFalse(m["safety"]["inconclusive_local_search_allowed"])

    def test_level2_artifact_is_immutable(self):
        with tempfile.TemporaryDirectory() as td:
            manga,ch,part=self.make_case(td)
            d=pw.l2dir(manga,ch.name); d.mkdir(parents=True)
            sentinel=d/"passed-001.png"; sentinel.write_bytes(b"immutable")
            before=sentinel.read_bytes()
            r=Level3Result(Level3Decision.UNSAFE,12000,
                "connected_component_crossing",0,13050,{},None)
            with patch("processamento.unificacao_imagens.image_stitcher_level3.search_local_safe_candidate",return_value=r):
                pw.process_merge_level3_pending(ch,part)
            self.assertEqual(sentinel.read_bytes(),before)

    def test_dedicated_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            manga,ch,part=self.make_case(td,1000)
            ok,_,m=pw.process_merge_level3_pending(ch,part)
            self.assertTrue(ok); self.assertEqual(len(m["safe_artifacts"]),1)
            mf=pw.l3dir(manga,ch.name)/"merge-level3-manifest.json"
            self.assertTrue(mf.is_file())
            self.assertEqual(json.loads(mf.read_text())["algorithm"],
                             "merge_level3_structural_safe_v1")

    def test_materialization_preserves_exact_global_offsets_across_sources(self):
        with tempfile.TemporaryDirectory() as td:
            manga=Path(td)/"manga"; ch=manga/"IMG"/"6"; ch.mkdir(parents=True)
            Image.new("RGB",(8,100),(255,0,0)).save(ch/"page-001.png")
            Image.new("RGB",(8,100),(0,0,255)).save(ch/"page-002.png")
            segment={
                "id":1,
                "global_start":50,
                "global_end":150,
                "source_spans":[
                    {
                        # source_spans preserva o global_start da fonte inteira;
                        # o recorte efetivo começa em source_y_start.
                        "file":"page-001.png",
                        "global_start":0,
                        "global_end":100,
                        "source_y_start":50,
                        "source_y_end":100,
                    },
                    {
                        "file":"page-002.png",
                        "global_start":100,
                        "global_end":150,
                        "source_y_start":0,
                        "source_y_end":50,
                    },
                ],
            }
            image=pw._materialize_level3_interval(ch,segment)
            self.assertEqual(image.size,(8,100))
            self.assertEqual(image.getpixel((0,0)),(255,0,0))
            self.assertEqual(image.getpixel((0,49)),(255,0,0))
            self.assertEqual(image.getpixel((0,50)),(0,0,255))
            self.assertEqual(image.getpixel((0,99)),(0,0,255))

if __name__=="__main__":
    unittest.main()
