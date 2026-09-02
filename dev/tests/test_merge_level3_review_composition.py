import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from processamento.unificacao_imagens import image_stitcher_review as rv


class Level3ReviewCompositionTests(unittest.TestCase):
    def _fixture(self):
        td=tempfile.TemporaryDirectory()
        manga=Path(td.name)/"manga"
        chapter="6"
        (manga/"IMG"/chapter).mkdir(parents=True)

        l2=manga/"FLUXO_SECUNDARIO"/"MERGE_LEVEL2"/chapter
        l3=manga/"FLUXO_SECUNDARIO"/"MERGE_LEVEL3"/chapter
        review=manga/"FLUXO_SECUNDARIO"/"MERGE_REVIEW"/chapter
        l2.mkdir(parents=True); l3.mkdir(parents=True); review.mkdir(parents=True)

        Image.new("RGB",(8,100),(10,10,10)).save(l2/"passed-001.png")
        Image.new("RGB",(8,60),(20,20,20)).save(l3/"safe-001.png")
        Image.new("RGB",(8,40),(30,30,30)).save(review/"merged-001.png")

        l2_payload={
            "schema_version":1,
            "algorithm":"merge_level2_auto_segments",
            "total_height":200,
            "segments":[{
                "id":1,"status":"passed","global_start":0,"global_end":100,
                "artifact":{"file":"passed-001.png"},
            }],
            "artifacts":[{
                "segment_id":1,"file":"passed-001.png",
                "global_start":0,"global_end":100,
            }],
            "pending_segments":[{
                "id":2,"status":"failed","global_start":100,"global_end":200,
            }],
        }
        l2_path=l2/"merge-level2-manifest.json"
        l2_path.write_text(json.dumps(l2_payload,indent=2)+"\n",encoding="utf-8")
        l2_hash=hashlib.sha256(l2_path.read_bytes()).hexdigest()

        l3_payload={
            "schema_version":1,
            "algorithm":"merge_level3_structural_safe_v1",
            "total_height":200,
            "source_level2_manifest":"merge-level2-manifest.json",
            "source_level2_sha256":l2_hash,
            "safe_artifacts":[{
                "file":"safe-001.png","global_start":100,"global_end":160,
                "height":60,"source_stage":"level3",
            }],
            "residual_pending_segments":[{
                "id":2,"global_start":160,"global_end":200,
                "status":"failed","validation":"review_required",
            }],
        }
        (l3/"merge-level3-manifest.json").write_text(
            json.dumps(l3_payload,indent=2)+"\n",encoding="utf-8"
        )

        review_payload={
            "schema_version":1,
            "scope":{"type":"pending_segments","intervals":[[160,200]]},
            "regions":[{
                "global_start":160,"global_end":200,
                "boundaries":[160,200],
                "outputs":["merged-001.png"],
            }],
        }
        (review/"merge-review.json").write_text(
            json.dumps(review_payload,indent=2)+"\n",encoding="utf-8"
        )
        return td,manga,chapter,review,review_payload,l2_path

    def test_composes_level2_level3_and_review_in_global_order(self):
        td,manga,chapter,review,payload,_=self._fixture()
        self.addCleanup(td.cleanup)
        with patch.object(rv.v3,"is_chapter_merged",return_value=True):
            ok,msg=rv._approve_scoped_level2_review(
                manga,chapter,review,payload
            )
        self.assertTrue(ok,msg)
        official=manga/"FLUXO_SECUNDARIO"/"MERGE"/chapter
        manifest=json.loads(
            (official/"merge-manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            manifest["algorithm"],
            "merge_level2_level3_review_composition_v1",
        )
        self.assertEqual(
            [x["source_stage"] for x in manifest["outputs"]],
            ["level2","level3","review"],
        )
        self.assertEqual(
            [(x["global_start"],x["global_end"]) for x in manifest["outputs"]],
            [(0,100),(100,160),(160,200)],
        )

    def test_rejects_review_that_targets_original_level2_pending(self):
        td,manga,chapter,review,payload,_=self._fixture()
        self.addCleanup(td.cleanup)
        payload["scope"]["intervals"]=[[100,200]]
        payload["regions"][0]["global_start"]=100
        payload["regions"][0]["boundaries"]=[100,200]
        with patch.object(rv.v3,"is_chapter_merged",return_value=True):
            ok,msg=rv._approve_scoped_level2_review(
                manga,chapter,review,payload
            )
        self.assertFalse(ok)
        self.assertIn("pending autoritativo",msg)
        self.assertFalse((manga/"FLUXO_SECUNDARIO"/"MERGE"/chapter).exists())

    def test_rejects_stale_level3_snapshot(self):
        td,manga,chapter,review,payload,l2_path=self._fixture()
        self.addCleanup(td.cleanup)
        data=json.loads(l2_path.read_text(encoding="utf-8"))
        data["changed_after_level3"]=True
        l2_path.write_text(json.dumps(data,indent=2)+"\n",encoding="utf-8")
        with patch.object(rv.v3,"is_chapter_merged",return_value=True):
            ok,msg=rv._approve_scoped_level2_review(
                manga,chapter,review,payload
            )
        self.assertFalse(ok)
        self.assertIn("desatualizado",msg)
        self.assertFalse((manga/"FLUXO_SECUNDARIO"/"MERGE"/chapter).exists())


if __name__=="__main__":
    unittest.main()
