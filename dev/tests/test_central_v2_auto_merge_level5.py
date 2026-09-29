import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from dev.tests.test_central_v2_auto_merge_level4 import CentralV2Level4Tests
from orquestracao.auto_merge.consulta_nivel5 import query_level5
from orquestracao.auto_merge.executar_nivel5 import execute_level5
from processamento.unificacao_imagens.auto_merge.nivel4 import read_level4
from central_v2.backend.routes.router import dispatch_get, dispatch_post


class CentralV2Level5Tests(unittest.TestCase):
    def make_case(self, root):
        manga, chapter, level3 = CentralV2Level4Tests().make_case(root)
        level4 = manga / "FLUXO_SECUNDARIO" / "01_MERGE_PROCESSAMENTO" / "MERGE_LEVEL4" / "6"
        level4.mkdir(parents=True)
        Image.new("RGB", (16, 100), "yellow").save(level4 / "l4.png")
        l3path = level3 / "merge-level3-manifest.json"
        (level4 / "merge-level4-manifest.json").write_text(json.dumps({
            "schema_version": 1, "algorithm": "merge_level4_directed_structural_safe_v1",
            "chapter": "6", "total_height": 14_000,
            "source_level3_sha256": hashlib.sha256(l3path.read_bytes()).hexdigest(),
            "safe_artifacts": [{"file": "l4.png", "global_start": 300, "global_end": 400}],
            "residual_pending_segments": [{"id": 1, "global_start": 400, "global_end": 14_000}],
        }))
        return manga, chapter, level4

    def result(self, *, partial=False):
        return {"resolved": not partial, "partial_resolved": partial,
                "boundaries": [400, 7_000] if partial else [400, 7_000, 14_000],
                "cuts": [7_000], "chunks": [6_600] if partial else [6_600, 7_000],
                "residual_start": 7_000 if partial else None,
                "residual_end": 14_000 if partial else None,
                "evaluated_candidates": 2, "eligible_candidates": 10, "safe_candidates": 1,
                "decision_counts": {"SAFE": 1}, "reason_counts": {},
                "selected_diagnostics": [{"selected_y": 7_000, "reason": "safe"}],
                "search_passes": 1}

    def test_reader_and_queue_accept_only_current_directed_level4(self):
        with tempfile.TemporaryDirectory() as root:
            manga, _, _ = self.make_case(root)
            self.assertEqual(read_level4(manga, "6").status, "recorded")
            row = query_level5(manga, ["6"])[0]
            self.assertEqual(row["residual_segments"], 1)
            self.assertEqual(row["residual_regions"], ["page-001.png → page-001.png"])
            self.assertNotIn("global_start", row)

    def test_rejects_stale_level4_provenance(self):
        with tempfile.TemporaryDirectory() as root:
            manga, _, level4 = self.make_case(root)
            path = level4 / "merge-level4-manifest.json"
            payload = json.loads(path.read_text())
            payload["source_level3_sha256"] = "stale"
            path.write_text(json.dumps(payload))
            document = read_level4(manga, "6")
            self.assertEqual(document.status, "invalid")
            self.assertIn("desatualizado", document.error)

    def test_routes_query_and_enqueue_level5(self):
        with tempfile.TemporaryDirectory() as root:
            self.make_case(root)
            response = dispatch_get("/api/auto-merge/level5?provider=ridi&manga=test-manga", Path(root))
            self.assertEqual(response.status, 200)
            self.assertEqual(json.loads(response.body)["chapters"][0]["chapter"], "6")
            with patch("central_v2.backend.routes.auto_merge.level5.legacy_server_active", return_value=False), patch(
                "central_v2.backend.routes.auto_merge.level5.submit",
                return_value={"id": "job-5", "status": "queued"},
            ) as submit:
                queued = dispatch_post("/api/auto-merge/level5/execute", {
                    "provider": "ridi", "manga": "test-manga", "chapters": ["6"],
                }, Path(root))
            self.assertEqual(queued.status, 202)
            self.assertEqual(submit.call_args.kwargs["total"], 1)

    def test_complete_composition_promotes_stages_one_through_five(self):
        with tempfile.TemporaryDirectory() as root:
            manga, _, _ = self.make_case(root)
            with patch("processamento.unificacao_imagens.auto_merge.planejamento_nivel5.find_global_safe_composition",
                       return_value=self.result()):
                result = execute_level5(manga, ["6"], "job-5", lambda *_: None)
            self.assertEqual(result[0]["status"], "promoted")
            official = manga / "FLUXO_SECUNDARIO" / "02_MERGE" / "6" / "merge-manifest.json"
            data = json.loads(official.read_text())
            self.assertEqual(data["algorithm"], "merge_auto_level2_level3_level4_level5_composition_v1")
            self.assertEqual([row["source_stage"] for row in data["outputs"]],
                             ["auto_merge", "level2", "level3", "level4", "level5", "level5"])

    def test_partial_safe_prefix_preserves_only_the_remaining_suffix_for_review(self):
        with tempfile.TemporaryDirectory() as root:
            manga, _, level4 = self.make_case(root)
            with patch("processamento.unificacao_imagens.auto_merge.planejamento_nivel5.find_global_safe_composition",
                       return_value=self.result(partial=True)):
                result = execute_level5(manga, ["6"], "job-5", lambda *_: None)
            self.assertEqual(result[0]["status"], "partial")
            self.assertEqual(result[0]["next_stage"], "Revisão Merge")
            stage = manga / "FLUXO_SECUNDARIO" / "01_MERGE_PROCESSAMENTO" / "MERGE_LEVEL5" / "6"
            data = json.loads((stage / "merge-level5-manifest.json").read_text())
            self.assertEqual([(row["global_start"], row["global_end"]) for row in data["safe_artifacts"]], [(400, 7_000)])
            self.assertEqual([(row["global_start"], row["global_end"]) for row in data["residual_pending_segments"]], [(7_000, 14_000)])
            self.assertFalse((manga / "FLUXO_SECUNDARIO" / "02_MERGE" / "6").exists())
            self.assertTrue((level4 / "merge-level4-manifest.json").is_file())


if __name__ == "__main__":
    unittest.main()
