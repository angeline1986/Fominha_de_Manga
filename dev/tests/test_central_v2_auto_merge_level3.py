import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageDraw

from orquestracao.auto_merge.consulta_nivel3 import query_level3
from orquestracao.auto_merge.executar_nivel3 import execute_level3
from processamento.unificacao_imagens.auto_merge.nivel2 import read_level2
from processamento.unificacao_imagens.auto_merge.materializacao_nivel3 import materialize_level3
from processamento.unificacao_imagens.image_stitcher import PageInfo
from processamento.unificacao_imagens.image_stitcher_level3 import Level3Decision, Level3Result
from central_v2.backend.routes.router import dispatch_get, dispatch_post


class CentralV2Level3Tests(unittest.TestCase):
    def make_case(self, root):
        manga = Path(root) / "ridi" / "test-manga"
        chapter = manga / "IMG" / "6"
        chapter.mkdir(parents=True)
        source = Image.new("RGB", (16, 13_050), "white")
        draw = ImageDraw.Draw(source)
        draw.rectangle((0, 0, 15, 79), fill=(255, 0, 0))
        draw.rectangle((0, 12_080, 15, 13_049), fill=(0, 0, 255))
        source.save(chapter / "page-001.png")

        level1 = manga / "FLUXO_SECUNDARIO" / "01_MERGE_PROCESSAMENTO" / "AUTO_MERGE" / "6"
        level1.mkdir(parents=True)
        Image.new("RGB", (16, 80), (255, 0, 0)).save(level1 / "auto-001.png")
        level1_data = {
            "schema_version": 1, "algorithm": "auto_merge_level1_resolved_segments",
            "chapter": "6", "total_height": 13_050,
            "artifacts": [{"file": "auto-001.png", "global_start": 0, "global_end": 80, "height": 80}],
            "pending_segments": [{"id": 2, "global_start": 80, "global_end": 13_050, "height": 12_970}],
        }
        level1_path = level1 / "auto-merge-manifest.json"
        level1_path.write_text(json.dumps(level1_data), encoding="utf-8")

        level2 = manga / "FLUXO_SECUNDARIO" / "01_MERGE_PROCESSAMENTO" / "MERGE_LEVEL2" / "6"
        level2.mkdir(parents=True)
        level2_data = {
            "schema_version": 3, "algorithm": "merge_level2_bounded_safe_path_v1",
            "chapter": "6", "total_height": 13_050,
            "source_level1_sha256": hashlib.sha256(level1_path.read_bytes()).hexdigest(),
            "artifacts": [], "pending_segments": [{"id": 1, "global_start": 80, "global_end": 13_050}],
        }
        (level2 / "merge-level2-manifest.json").write_text(json.dumps(level2_data), encoding="utf-8")
        return manga, chapter, level1, level2, level1_path

    def safe_candidate(self, gray, *, candidate_y, region, image_global_start, config):
        return Level3Result(Level3Decision.SAFE, candidate_y,
                            "structurally_clear_uniform_band", region.global_start,
                            region.global_end, {"edge_density": 0}, None)

    def test_query_reads_only_a_provenanced_level2_residual(self):
        with tempfile.TemporaryDirectory() as root:
            manga, _, _, _, _ = self.make_case(root)
            document = read_level2(manga, "6")
            self.assertEqual(document.status, "recorded")
            rows = query_level3(manga, ["6"])
            self.assertEqual(rows[0]["residual_images"], 1)
            self.assertEqual(rows[0]["residual_regions"], ["page-001.png → page-001.png"])
            self.assertNotIn("global_start", rows[0])

    def test_rejects_stale_level2_manifest(self):
        with tempfile.TemporaryDirectory() as root:
            manga, _, _, level2, _ = self.make_case(root)
            path = level2 / "merge-level2-manifest.json"
            data = json.loads(path.read_text())
            data["source_level1_sha256"] = "stale"
            path.write_text(json.dumps(data), encoding="utf-8")
            document = read_level2(manga, "6")
            self.assertEqual(document.status, "invalid")
            self.assertIn("desatualizado", document.error)

    def test_http_routes_query_and_enqueue_level3(self):
        with tempfile.TemporaryDirectory() as root:
            self.make_case(root)
            output_root = Path(root)
            response = dispatch_get(
                "/api/auto-merge/level3?provider=ridi&manga=test-manga", output_root,
            )
            self.assertEqual(response.status, 200)
            self.assertEqual(json.loads(response.body)["chapters"][0]["chapter"], "6")
            with patch("central_v2.backend.routes.auto_merge.level3.legacy_server_active",
                       return_value=False), patch(
                "central_v2.backend.routes.auto_merge.level3.submit",
                return_value={"id": "job-1", "status": "queued"},
            ) as submit:
                queued = dispatch_post("/api/auto-merge/level3/execute", {
                    "provider": "ridi", "manga": "test-manga", "chapters": ["6"],
                }, output_root)
            self.assertEqual(queued.status, 202)
            self.assertEqual(json.loads(queued.body)["job"]["id"], "job-1")
            self.assertEqual(submit.call_args.kwargs["total"], 1)

    def test_resolves_and_promotes_complete_composition_without_rerendering_lower_levels(self):
        with tempfile.TemporaryDirectory() as root:
            manga, chapter, level1, level2, _ = self.make_case(root)
            original = (chapter / "page-001.png").read_bytes()
            events = []
            with patch("processamento.unificacao_imagens.auto_merge.planejamento_nivel3.search_local_safe_candidate",
                       side_effect=self.safe_candidate):
                result = execute_level3(manga, ["6"], "job-level3",
                                        lambda name, event: events.append(event))
            self.assertEqual(result[0]["status"], "promoted")
            self.assertEqual(result[0]["resolved_segments"], 2)
            self.assertEqual((chapter / "page-001.png").read_bytes(), original)
            level3 = manga / "FLUXO_SECUNDARIO" / "01_MERGE_PROCESSAMENTO" / "MERGE_LEVEL3" / "6"
            manifest = json.loads((level3 / "merge-level3-manifest.json").read_text())
            self.assertEqual(manifest["source_level2_sha256"], hashlib.sha256((level2 / "merge-level2-manifest.json").read_bytes()).hexdigest())
            self.assertEqual([(x["global_start"], x["global_end"]) for x in manifest["safe_artifacts"]],
                             [(80, 12_080), (12_080, 13_050)])
            history = query_level3(manga, ["6"], include_history=True)
            self.assertEqual(history[0]["status"], "Resolvido")
            self.assertFalse(history[0]["eligible"])
            response = dispatch_get("/api/auto-merge/level3?provider=ridi&manga=test-manga", Path(root))
            self.assertEqual(response.status, 200)
            self.assertEqual(json.loads(response.body)["chapters"][0]["status"], "Resolvido")
            official = manga / "FLUXO_SECUNDARIO" / "02_MERGE" / "6" / "merge-manifest.json"
            final = json.loads(official.read_text())
            self.assertEqual(final["algorithm"], "merge_auto_level2_level3_composition_v2")
            self.assertEqual([(x["global_start"], x["global_end"]) for x in final["outputs"]],
                             [(0, 80), (80, 12_080), (12_080, 13_050)])
            self.assertTrue(any(event.get("stage") == "promote" for event in events))
            self.assertTrue((level1 / "auto-001.png").is_file())

    def test_inconclusive_search_remains_pending_and_does_not_promote(self):
        with tempfile.TemporaryDirectory() as root:
            manga, _, _, _, _ = self.make_case(root)
            result = Level3Result(Level3Decision.INCONCLUSIVE, 12_080,
                                  "structural_evidence_inconclusive", 80, 13_050, {}, None)
            with patch("processamento.unificacao_imagens.auto_merge.planejamento_nivel3.search_local_safe_candidate",
                       return_value=result):
                output = execute_level3(manga, ["6"], "job-level3", lambda *_: None)
            self.assertEqual(output[0]["status"], "partial")
            self.assertEqual(output[0]["resolved_segments"], 0)
            self.assertEqual(output[0]["residuals"], [{"global_start": 80, "global_end": 13_050}])
            self.assertFalse((manga / "FLUXO_SECUNDARIO" / "02_MERGE" / "6").exists())
            history = query_level3(manga, ["6"], include_history=True)
            self.assertEqual(history[0]["status"], "Parcial")
            self.assertEqual(history[0]["residual_images"], 1)
            self.assertFalse(history[0]["eligible"])
            stage = manga / "FLUXO_SECUNDARIO" / "01_MERGE_PROCESSAMENTO" / "MERGE_LEVEL3" / "6"
            manifest = stage / "merge-level3-manifest.json"
            before = manifest.read_bytes()
            with self.assertRaisesRegex(ValueError, "sem residual elegível"):
                execute_level3(manga, ["6"], "retry-level3", lambda *_: None)
            self.assertEqual(manifest.read_bytes(), before)

    def test_materialization_preserves_source_offsets_across_pages(self):
        with tempfile.TemporaryDirectory() as root:
            chapter = Path(root) / "IMG" / "6"
            chapter.mkdir(parents=True)
            Image.new("RGB", (8, 100), (255, 0, 0)).save(chapter / "page-001.png")
            Image.new("RGB", (8, 100), (0, 0, 255)).save(chapter / "page-002.png")
            infos = [PageInfo(chapter / "page-001.png", 8, 100, 0, 100),
                     PageInfo(chapter / "page-002.png", 8, 100, 100, 200)]
            stage = Path(root) / "MERGE_LEVEL3" / "6"
            artifacts = materialize_level3(chapter, infos, [{
                "global_start": 50, "global_end": 150,
                "source_segment_id": 1, "decision_reason": "test-safe",
            }], stage)
            with Image.open(stage / artifacts[0]["file"]) as image:
                self.assertEqual(image.size, (8, 100))
                self.assertEqual(image.getpixel((0, 0)), (255, 0, 0))
                self.assertEqual(image.getpixel((0, 49)), (255, 0, 0))
                self.assertEqual(image.getpixel((0, 50)), (0, 0, 255))
                self.assertEqual(image.getpixel((0, 99)), (0, 0, 255))


if __name__ == "__main__":
    unittest.main()
