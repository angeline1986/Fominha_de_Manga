import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from interface_web import processing_web as web


class MergeLevel3UiContractTests(unittest.TestCase):

    def _fixture(self):
        td=tempfile.TemporaryDirectory()
        manga=Path(td.name)/"Manga"
        chapter=manga/"IMG"/"1"
        chapter.mkdir(parents=True)
        l2=web.l2dir(manga,"1")
        l3=web.l3dir(manga,"1")
        l2.mkdir(parents=True)
        l3.mkdir(parents=True)

        l2_manifest=l2/"merge-level2-manifest.json"
        l2_manifest.write_text('{"algorithm":"merge_level2_auto_segments"}\n',encoding="utf-8")
        digest=hashlib.sha256(l2_manifest.read_bytes()).hexdigest()

        failure={
            "status":"partial",
            "level2_status":"validated",
            "partition":{
                "level2_validated":True,
                "total_height":200,
                "resolved_segments":[
                    {"global_start":0,"global_end":100},
                ],
                "pending_segments":[
                    {"id":2,"global_start":100,"global_end":200},
                ],
            },
        }
        payload={
            "schema_version":1,
            "algorithm":"merge_level3_structural_safe_v1",
            "chapter":"1",
            "total_height":200,
            "source_level2_manifest":"merge-level2-manifest.json",
            "source_level2_sha256":digest,
            "safe_artifacts":[
                {
                    "file":"safe-001.png",
                    "global_start":100,
                    "global_end":150,
                    "height":50,
                    "source_segment_id":2,
                    "decision_reason":"safe_candidate",
                }
            ],
            "residual_pending_segments":[
                {
                    "global_start":150,
                    "global_end":200,
                    "height":50,
                    "source_segment_id":2,
                    "reason":"continuous_scene_too_long",
                    "trigger_reason":"strong_diagonal_crossing",
                    "trigger_decision":"UNSAFE",
                    "guard_metrics":{
                        "region_height":50,
                        "continuous_scene_max_height":30,
                    },
                }
            ],
            "diagnostics":[
                {
                    "source_segment_id":2,
                    "candidate_global_y":150,
                    "decision":"UNSAFE",
                    "reason":"strong_diagonal_crossing",
                    "metrics":{
                        "local_candidates_evaluated":200,
                        "safe_alternatives_found":0,
                        "local_decision_counts":{"UNSAFE":200},
                        "local_reason_counts":{"strong_diagonal_crossing":200},
                        "local_metric_ranges":{
                            "edge_density":{"min":0.021,"max":0.062},
                        },
                    },
                }
            ],
            "safety":{
                "level2_passed_artifacts_modified":False,
                "forced_cut":False,
                "inconclusive_local_search_allowed":False,
            },
        }
        (l3/"merge-level3-manifest.json").write_text(
            json.dumps(payload,ensure_ascii=False,indent=2)+"\n",
            encoding="utf-8",
        )
        return td,manga,chapter,failure,l2_manifest

    def test_valid_level3_detail_exposes_persisted_diagnostics(self):
        td,manga,chapter,failure,_=self._fixture()
        self.addCleanup(td.cleanup)

        detail=web._level3_ui_detail(manga,chapter,failure)

        self.assertTrue(detail["available"])
        self.assertTrue(detail["valid"])
        self.assertIsNone(detail["error"])
        self.assertEqual(detail["safe_artifacts_count"],1)
        self.assertEqual(detail["residual_pending_segments_count"],1)
        self.assertEqual(
            detail["review_pending_segments"],
            [{"global_start":150,"global_end":200,"height":50,"source_segment_id":2,
              "reason":"continuous_scene_too_long","trigger_reason":"strong_diagonal_crossing",
              "trigger_decision":"UNSAFE","guard_metrics":{"region_height":50,"continuous_scene_max_height":30}}],
        )
        metrics=detail["diagnostics"][0]["metrics"]
        self.assertEqual(metrics["local_candidates_evaluated"],200)
        self.assertEqual(metrics["local_decision_counts"],{"UNSAFE":200})
        self.assertIn("edge_density",metrics["local_metric_ranges"])

    def test_stale_level3_detail_fails_closed(self):
        td,manga,chapter,failure,l2_manifest=self._fixture()
        self.addCleanup(td.cleanup)

        l2_manifest.write_text('{"algorithm":"merge_level2_auto_segments","changed":true}\n',encoding="utf-8")
        detail=web._level3_ui_detail(manga,chapter,failure)

        self.assertTrue(detail["available"])
        self.assertFalse(detail["valid"])
        self.assertIn("desatualizado",detail["error"])
        self.assertNotIn("diagnostics",detail)

    def test_row_state_exposes_level3_detail_without_changing_state_rules(self):
        with tempfile.TemporaryDirectory() as td:
            manga=Path(td)/"Manga"
            chapter=manga/"IMG"/"1"
            chapter.mkdir(parents=True)
            failure={
                "status":"partial",
                "level2_status":"validated",
                "partition":{
                    "level2_validated":True,
                    "resolved_segments":[{"global_start":0,"global_end":100}],
                    "pending_segments":[{"global_start":100,"global_end":200}],
                },
            }
            sentinel={"available":True,"valid":True,"diagnostics":[{"reason":"x"}]}
            with patch.object(web,"read_merge_failure",return_value=failure), \
                 patch.object(web,"review_merge_items",return_value=[]), \
                 patch.object(web,"_level3_ui_detail",return_value=sentinel):
                state=web.row_state(manga,chapter)

            self.assertEqual(state["merge_level3_detail"],sentinel)
            self.assertTrue(state["merge_level2_validated"])
            self.assertFalse(state["needs_review"])


if __name__ == "__main__":
    unittest.main()
