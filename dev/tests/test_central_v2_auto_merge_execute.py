import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from PIL import Image

from central_v2.backend.routes.router import dispatch_get, dispatch_post
from orquestracao.auto_merge.executar_nivel1 import execute_level1
from processamento.unificacao_imagens.image_stitcher import is_chapter_merged


class Level1ExecutionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.output = Path(temporary.name) / "output"
        self.manga = self.output / "comix" / "Obra Teste"
        self.chapter = self.manga / "IMG" / "1"
        self.chapter.mkdir(parents=True)
        Image.new("RGB", (8, 120), "white").save(self.chapter / "page-001.png")

    def submit(self, chapters=("1",)):
        with patch("central_v2.backend.routes.auto_merge_execute.legacy_server_active", return_value=False):
            response = dispatch_post("/api/auto-merge/level1/execute", {
                "provider": "comix", "manga": "Obra Teste", "chapters": list(chapters),
            }, self.output)
        return response, json.loads(response.body)

    def wait_job(self, job_id):
        for _ in range(200):
            response = dispatch_get(f"/api/jobs/{job_id}", self.output)
            job = json.loads(response.body)["job"]
            if job["status"] in {"completed", "failed"}:
                return job
            time.sleep(0.01)
        self.fail("Job não terminou no prazo do teste.")

    def test_complete_plan_runs_as_job_and_promotes_official_merge(self):
        response, payload = self.submit()
        self.assertEqual(response.status, 202)
        job = self.wait_job(payload["job"]["id"])
        self.assertEqual(job["status"], "completed", job["error"])
        self.assertEqual(job["results"][0]["status"], "promoted")
        self.assertEqual(job["progress"]["percent"], 100)
        self.assertEqual(job["progress"]["completed"], 1)
        self.assertTrue(is_chapter_merged(self.chapter))
        events = self.manga / "FLUXO_SECUNDARIO" / "PROCESSING_LOG" / "auto-merge-level1-events.jsonl"
        self.assertEqual(len(events.read_text().splitlines()), 2)

    def test_invalid_selection_is_rejected_without_writes(self):
        response, payload = self.submit(("../fora-da-obra",))
        self.assertEqual(response.status, 400)
        self.assertIn("fora da obra", payload["error"])
        self.assertEqual(set(self.manga.rglob("*")), {self.manga / "IMG", self.chapter, self.chapter / "page-001.png"})

    def test_active_v1_blocks_job_creation(self):
        with patch("central_v2.backend.routes.auto_merge_execute.legacy_server_active", return_value=True):
            response = dispatch_post("/api/auto-merge/level1/execute", {
                "provider": "comix", "manga": "Obra Teste", "chapters": ["1"],
            }, self.output)
        self.assertEqual(response.status, 400)
        self.assertIn("Central V1", json.loads(response.body)["error"])
        self.assertFalse((self.manga / "FLUXO_SECUNDARIO").exists())

    def test_occupied_chapter_is_reported_and_later_chapter_continues(self):
        occupied = self.manga / "FLUXO_SECUNDARIO" / "02_MERGE" / "1"
        occupied.mkdir(parents=True)
        sentinel = occupied / "keep.txt"
        sentinel.write_text("preserve")
        second = self.manga / "IMG" / "2"
        second.mkdir()
        Image.new("RGB", (8, 120), "white").save(second / "page-001.png")

        response, payload = self.submit(("1", "2"))
        self.assertEqual(response.status, 202)
        job = self.wait_job(payload["job"]["id"])
        self.assertEqual(job["status"], "completed")
        self.assertEqual([item["status"] for item in job["results"]], ["failed", "promoted"])
        self.assertEqual(sentinel.read_text(), "preserve")
        self.assertTrue(is_chapter_merged(second))

    def test_selected_chapters_run_in_parallel_and_report_aggregate_progress(self):
        names = ["1", "2", "3"]
        for name in names[1:]:
            chapter = self.manga / "IMG" / name
            chapter.mkdir()
            Image.new("RGB", (8, 120), "white").save(chapter / "page-001.png")
        barrier = threading.Barrier(3)
        progress_events = []

        def process(manga, chapter, job_id, report):
            barrier.wait(timeout=3)
            report(chapter, {"stage": "analyze_pages", "current": 1, "total": 1, "message": "Análise concluída"})
            return {"chapter": chapter, "status": "promoted"}

        with patch("orquestracao.auto_merge.executar_nivel1._run_chapter", side_effect=process):
            results = execute_level1(self.manga, names, "job", lambda chapter, event: progress_events.append(event))

        self.assertEqual(len(results), 3)
        self.assertEqual(progress_events[-1]["percent"], 100)
        self.assertEqual(progress_events[-1]["completed"], 3)


if __name__ == "__main__":
    unittest.main()
