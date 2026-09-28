import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from central_v2.backend.routes.balanceamento import balanceamento_job_response
from central_v2.backend.routes.balanceamento_media import balanceamento_image_response
from central_v2.backend.routes.router import dispatch_get


class BalanceamentoV2Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.manga = self.root / "comix" / "Teste"
        (self.manga / "IMG").mkdir(parents=True)

    def tearDown(self):
        self.temp.cleanup()

    def test_get_balance_state_does_not_write_validation_manifests(self):
        chapter = self.manga / "FLUXO_SECUNDARIO/02_MERGE/1"
        chapter.mkdir(parents=True)
        (chapter / "page-001.png").write_bytes(b"fixture")
        analysis = {"chapter": "1", "status": "BALANCEADO", "merge_count": 1,
                    "issues_count": 0, "merges": [], "issues": []}
        with patch("processamento.balanceamento.balanceamento._chapter_analysis", return_value=analysis), \
                patch("processamento.balanceamento.balanceamento._latest_proposal", return_value=None):
            response = dispatch_get("/api/balanceamento?provider=comix&manga=Teste", self.root)
        payload = json.loads(response.body)
        self.assertEqual(response.status, 200)
        self.assertEqual(payload["chapters"][0]["chapter"], "1")
        self.assertFalse((self.manga / "FLUXO_SECUNDARIO/01_MERGE_PROCESSAMENTO/BALANCE_VALIDATION").exists())

    def test_validate_is_an_explicit_background_job(self):
        created = {}
        fake_job = {"id": "a" * 32, "status": "queued"}
        with patch("central_v2.backend.routes.balanceamento.legacy_server_active", return_value=False), \
                patch("central_v2.backend.routes.balanceamento.submit", side_effect=lambda operation, total: created.update(operation=operation) or fake_job), \
                patch("central_v2.backend.routes.balanceamento.validate_state", return_value={"ok": True}) as validate:
            response = balanceamento_job_response("validate", {"provider": "comix", "manga": "Teste"}, self.root)
            results = created["operation"](lambda *_: None, "job")
        self.assertEqual(response.status, 202)
        self.assertEqual(json.loads(response.body)["job"]["id"], fake_job["id"])
        self.assertEqual(results[0]["data"], {"ok": True})
        validate.assert_called_once()

    def test_balance_image_requires_a_manifest_declared_file(self):
        chapter = self.manga / "FLUXO_SECUNDARIO/02_MERGE/1"
        chapter.mkdir(parents=True)
        image = chapter / "merge-001.png"
        image.write_bytes(b"pixels")
        (chapter / "merge-manifest.json").write_text(json.dumps({"outputs": [{"file": image.name}]}))
        query = {key: [value] for key, value in {
            "provider": "comix", "manga": "Teste", "chapter": "1",
            "file": image.name, "kind": "merge",
        }.items()}
        allowed = balanceamento_image_response(query, self.root)
        query["file"] = ["other.png"]
        denied = balanceamento_image_response(query, self.root)
        query["file"] = [image.name]
        query["chapter"] = [".."]
        traversal = balanceamento_image_response(query, self.root)
        self.assertEqual(allowed.status, 200)
        self.assertEqual(denied.status, 404)
        self.assertEqual(traversal.status, 404)


if __name__ == "__main__":
    unittest.main()
