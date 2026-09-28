import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from orquestracao.auto_merge.consulta_nivel4 import query_level4
from orquestracao.auto_merge.executar_nivel4 import execute_level4
from processamento.unificacao_imagens.auto_merge.nivel3 import read_level3
from central_v2.backend.routes.router import dispatch_get, dispatch_post


class CentralV2Level4Tests(unittest.TestCase):
    def make_case(self, root):
        manga = Path(root) / "ridi" / "test-manga"
        chapter = manga / "IMG" / "6"
        chapter.mkdir(parents=True)
        Image.new("RGB", (16, 14_000), "white").save(chapter / "page-001.png")
        base = manga / "FLUXO_SECUNDARIO" / "01_MERGE_PROCESSAMENTO"
        level1, level2, level3 = [base / folder / "6" for folder in ("AUTO_MERGE", "MERGE_LEVEL2", "MERGE_LEVEL3")]
        for folder in (level1, level2, level3):
            folder.mkdir(parents=True)
        Image.new("RGB", (16, 100), "red").save(level1 / "auto.png")
        (level1 / "auto-merge-manifest.json").write_text(json.dumps({
            "schema_version": 1, "algorithm": "auto_merge_level1_resolved_segments",
            "chapter": "6", "total_height": 14_000,
            "artifacts": [{"file": "auto.png", "global_start": 0, "global_end": 100}],
            "pending_segments": [{"global_start": 100, "global_end": 14_000}],
        }))
        Image.new("RGB", (16, 100), "blue").save(level2 / "l2.png")
        l1path = level1 / "auto-merge-manifest.json"
        (level2 / "merge-level2-manifest.json").write_text(json.dumps({
            "schema_version": 3, "algorithm": "merge_level2_bounded_safe_path_v1",
            "chapter": "6", "total_height": 14_000,
            "source_level1_sha256": hashlib.sha256(l1path.read_bytes()).hexdigest(),
            "artifacts": [{"file": "l2.png", "global_start": 100, "global_end": 200}],
            "pending_segments": [{"global_start": 200, "global_end": 14_000}],
        }))
        Image.new("RGB", (16, 100), "green").save(level3 / "l3.png")
        l2path = level2 / "merge-level2-manifest.json"
        (level3 / "merge-level3-manifest.json").write_text(json.dumps({
            "schema_version": 1, "algorithm": "merge_level3_structural_safe_v1",
            "chapter": "6", "total_height": 14_000,
            "source_level2_sha256": hashlib.sha256(l2path.read_bytes()).hexdigest(),
            "safe_artifacts": [{"file": "l3.png", "global_start": 200, "global_end": 300}],
            "residual_pending_segments": [{"id": 1, "global_start": 300, "global_end": 14_000}],
        }))
        return manga, chapter, level3

    def test_reader_and_queue_require_valid_level3_residual(self):
        with tempfile.TemporaryDirectory() as root:
            manga, _, _ = self.make_case(root)
            self.assertEqual(read_level3(manga, "6").status, "recorded")
            row = query_level4(manga, ["6"])[0]
            self.assertEqual(row["residual_segments"], 1)
            self.assertEqual(row["residual_regions"], ["page-001.png → page-001.png"])
            self.assertNotIn("global_start", row)

    def test_http_routes_query_and_enqueue_level4(self):
        with tempfile.TemporaryDirectory() as root:
            self.make_case(root)
            output_root = Path(root)
            response = dispatch_get("/api/auto-merge/level4?provider=ridi&manga=test-manga", output_root)
            self.assertEqual(response.status, 200)
            self.assertEqual(json.loads(response.body)["chapters"][0]["chapter"], "6")
            with patch("central_v2.backend.routes.auto_merge_level4_execute.legacy_server_active", return_value=False), patch(
                "central_v2.backend.routes.auto_merge_level4_execute.submit",
                return_value={"id": "job-4", "status": "queued"},
            ) as submit:
                queued = dispatch_post("/api/auto-merge/level4/execute", {
                    "provider": "ridi", "manga": "test-manga", "chapters": ["6"],
                }, output_root)
            self.assertEqual(queued.status, 202)
            self.assertEqual(json.loads(queued.body)["job"]["id"], "job-4")
            self.assertEqual(submit.call_args.kwargs["total"], 1)

    def test_global_safe_composition_promotes_all_four_stages(self):
        with tempfile.TemporaryDirectory() as root:
            manga, chapter, level3 = self.make_case(root)
            plan = {"resolved": True, "boundaries": [300, 7_000, 14_000], "cuts": [7_000],
                    "chunks": [6_700, 7_000], "evaluated_candidates": 2,
                    "eligible_candidates": 10, "safe_candidates": 1,
                    "decision_counts": {"SAFE": 1}, "reason_counts": {},
                    "selected_diagnostics": [{"selected_y": 7_000, "reason": "safe"}],
                    "search_passes": 1, "strategy": "directed_coarse_refine_v1", "preselection": {}}
            with patch("processamento.unificacao_imagens.auto_merge.planejamento_nivel4.find_global_safe_composition", return_value=plan):
                result = execute_level4(manga, ["6"], "job-4", lambda *_: None)
            self.assertEqual(result[0]["status"], "promoted")
            self.assertEqual(result[0]["resolved_segments"], 2)
            official = manga / "FLUXO_SECUNDARIO" / "02_MERGE" / "6" / "merge-manifest.json"
            data = json.loads(official.read_text())
            self.assertEqual(data["algorithm"], "merge_auto_level2_level3_level4_composition_v1")
            self.assertEqual([row["source_stage"] for row in data["outputs"]], ["auto_merge", "level2", "level3", "level4", "level4"])
            self.assertTrue((level3 / "merge-level3-manifest.json").is_file())

    def test_unresolved_global_path_is_preserved_for_level_v(self):
        with tempfile.TemporaryDirectory() as root:
            manga, _, _ = self.make_case(root)
            plan = {"resolved": False, "boundaries": None, "cuts": [], "chunks": [],
                    "evaluated_candidates": 3, "eligible_candidates": 10,
                    "safe_candidates": 0, "decision_counts": {"INCONCLUSIVE": 3},
                    "reason_counts": {"uncertain": 3}, "selected_diagnostics": [],
                    "search_passes": 1, "strategy": "directed_coarse_refine_v1", "preselection": {}}
            with patch("processamento.unificacao_imagens.auto_merge.planejamento_nivel4.find_global_safe_composition", return_value=plan):
                result = execute_level4(manga, ["6"], "job-4", lambda *_: None)
            self.assertEqual(result[0]["status"], "partial")
            self.assertEqual(result[0]["next_stage"], "Auto-Merge Nível V")
            self.assertFalse((manga / "FLUXO_SECUNDARIO" / "02_MERGE" / "6").exists())


if __name__ == "__main__":
    unittest.main()
