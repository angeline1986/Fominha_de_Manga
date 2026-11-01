"""Fluxo real de análise, prévia e correção de dimensões da V2."""

import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from PIL import Image

from central_v2.backend.jobs.manager import get_job
from central_v2.backend.routes.image_validation import (
    analyze_response, apply_response, image_response, state_response,
)
from central_v2.backend.routes.get_dispatch import dispatch_get
from central_v2.backend.routes.post_dispatch import dispatch_post
from processamento.validacao_imagens.corretor_dimensoes import corrigir_imagem


class ImageValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.chapter = self.root / "comix" / "Obra" / "IMG" / "1"
        self.chapter.mkdir(parents=True)
        for number, width in enumerate((720, 720, 50), 1):
            Image.new("RGB", (width, 41), "white").save(self.chapter / f"page-{number:03}.png")
        self.context = {"provider": "comix", "manga": "Obra"}

    def wait_job(self, response):
        self.assertEqual(response.status, 202)
        job_id = json.loads(response.body)["job"]["id"]
        for _ in range(100):
            job = get_job(job_id)
            if job["status"] in {"completed", "failed"}:
                return job
            time.sleep(.02)
        self.fail("Job não terminou.")

    def state(self):
        query = {key: [value] for key, value in self.context.items()}
        response = state_response(query, self.root)
        self.assertEqual(response.status, 200)
        return json.loads(response.body)["chapters"][0]

    def test_execute_preview_and_apply_preserves_original(self):
        self.assertEqual(self.state()["status"], "pending")
        job = self.wait_job(analyze_response({**self.context, "chapters": ["1"]}, self.root))
        self.assertEqual(job["status"], "completed")
        row = self.state()
        self.assertEqual((row["status"], row["exceptions"]), ("review", 1))
        self.assertEqual([item["file"] for item in row["images"]], ["page-003.png"])
        query = {**{key: [value] for key, value in self.context.items()},
                 "chapter": ["1"], "file": ["page-003.png"], "variant": ["proposed"]}
        preview = image_response(query, self.root)
        self.assertEqual(preview.status, 200)
        self.assertEqual(image_response({**query, "file": ["page-001.png"]}, self.root).status, 400)
        from io import BytesIO
        with Image.open(BytesIO(preview.body)) as image:
            self.assertEqual(image.size, (720, 590))
        with patch("central_v2.backend.routes.image_validation.legacy_server_active", return_value=False):
            job = self.wait_job(apply_response({**self.context, "chapter": "1", "file": "page-003.png"}, self.root))
        self.assertEqual(job["status"], "completed", job["error"])
        with Image.open(self.chapter / "page-003_old.png") as original:
            self.assertEqual(original.size, (50, 41))
        with Image.open(self.chapter / "page-003.png") as corrected:
            self.assertEqual(corrected.size, (720, 590))
        self.assertEqual(self.state()["status"], "applied")

    def test_stale_analysis_hides_review_and_blocks_apply(self):
        self.wait_job(analyze_response({**self.context, "chapters": ["1"]}, self.root))
        Image.new("RGB", (40, 41), "black").save(self.chapter / "page-003.png")
        self.assertEqual(self.state()["status"], "pending")
        with patch("central_v2.backend.routes.image_validation.legacy_server_active", return_value=False):
            response = apply_response({**self.context, "chapter": "1", "file": "page-003.png"}, self.root)
        self.assertEqual(response.status, 400)
        self.assertFalse((self.chapter / "page-003_old.png").exists())

    def test_existing_backup_is_never_overwritten(self):
        backup = self.chapter / "page-003_old.png"
        backup.write_bytes(b"preserve")
        with self.assertRaisesRegex(ValueError, "já existe"):
            corrigir_imagem(self.chapter / "page-003.png", (50, 41), 720)
        self.assertEqual(backup.read_bytes(), b"preserve")
        with Image.open(self.chapter / "page-003.png") as original:
            self.assertEqual(original.size, (50, 41))

    def test_unreadable_image_is_attention_without_eye_candidate(self):
        (self.chapter / "page-003.png").write_bytes(b"invalid image")
        job = self.wait_job(analyze_response({**self.context, "chapters": ["1"]}, self.root))
        self.assertEqual(job["status"], "completed")
        row = self.state()
        self.assertEqual(row["status"], "attention")
        self.assertEqual(row["images"], [])

    def test_http_dispatch_reaches_validation_contract(self):
        response = dispatch_get("/api/images/validation?provider=comix&manga=Obra", self.root)
        self.assertEqual(response.status, 200)
        self.assertEqual(json.loads(response.body)["chapters"][0]["status"], "pending")
        started = dispatch_post("/api/images/validation/analyze",
                                {**self.context, "chapters": ["1"]}, self.root)
        self.assertEqual(self.wait_job(started)["status"], "completed")
        response = dispatch_get("/api/images/validation?provider=comix&manga=Obra", self.root)
        self.assertEqual(json.loads(response.body)["chapters"][0]["status"], "review")


if __name__ == "__main__":
    unittest.main()
