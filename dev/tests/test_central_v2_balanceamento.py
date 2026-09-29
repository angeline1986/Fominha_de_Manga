import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image

from central_v2.backend.routes.balanceamento import balanceamento_job_response
from central_v2.backend.routes.balanceamento_media import balanceamento_image_response
from central_v2.backend.routes.router import dispatch_get
from processamento.balanceamento.balanceador import (
    effect_manual_balance,
    generate_manual_balance,
    prepare_manual_balance,
)


class BalanceamentoV2Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
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

    def test_prepare_editor_stitches_selected_merges_and_returns_merge_ranges(self):
        source = self.manga / "IMG" / "3"
        source.mkdir(parents=True)
        merge_dir = self.manga / "FLUXO_SECUNDARIO/02_MERGE/3"
        merge_dir.mkdir(parents=True)
        colors = [(220, 10, 10), (210, 20, 20), (10, 20, 220), (20, 30, 210)]
        for index, color in enumerate(colors, start=1):
            Image.new("RGB", (3, 2), color).save(source / f"page-{index:03}.png")
        Image.new("RGB", (3, 4)).save(merge_dir / "merge-a.png")
        Image.new("RGB", (3, 4)).save(merge_dir / "merge-b.png")
        (merge_dir / "merge-manifest.json").write_text(json.dumps({"outputs": [
            {"file": "merge-a.png", "global_start": 0, "global_end": 4, "width": 3, "height": 4},
            {"file": "merge-b.png", "global_start": 4, "global_end": 8, "width": 3, "height": 4},
        ], "source_total_height": 8, "validation": {"ok": True, "errors": []}}))
        for filename, upper, lower in (("merge-a.png", colors[0], colors[1]), ("merge-b.png", colors[2], colors[3])):
            image = Image.new("RGB", (3, 4))
            image.paste(Image.new("RGB", (3, 2), upper), (0, 0))
            image.paste(Image.new("RGB", (3, 2), lower), (0, 2))
            image.save(merge_dir / filename)

        payload = prepare_manual_balance(self.manga, "3", ["merge-a.png", "merge-b.png"])
        self.assertEqual(payload["merge_ranges"], [
            {"file": "merge-a.png", "global_start": 0, "global_end": 4},
            {"file": "merge-b.png", "global_start": 4, "global_end": 8},
        ])
        self.assertEqual([item["file"] for item in payload["source_slices"]], [
            "page-001.png", "page-002.png", "page-003.png", "page-004.png",
        ])
        preview = self.manga / "FLUXO_SECUNDARIO/01_MERGE_PROCESSAMENTO/BALANCE_EDITOR/3/manual-source.png"
        with Image.open(preview) as image:
            self.assertEqual(image.size, (3, 8))
            self.assertEqual(image.getpixel((0, 0)), colors[0])
            self.assertEqual(image.getpixel((0, 4)), colors[2])

        proposal = generate_manual_balance(self.manga, "3", ["merge-a.png", "merge-b.png"], [3, 5])
        result = effect_manual_balance(self.manga, "3")
        self.assertEqual(result["status"], "EFETIVADO")
        self.assertEqual(result["output_count"], 3)
        manifest = json.loads((merge_dir / "merge-manifest.json").read_text())
        self.assertEqual(manifest["source_width"], 3)
        self.assertEqual(len(manifest["outputs"]), 3)
        with Image.open(merge_dir / proposal["artifacts"][0]["file"]) as image:
            self.assertEqual(image.width, 3)


if __name__ == "__main__":
    unittest.main()
