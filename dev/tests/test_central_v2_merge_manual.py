import json
import hashlib
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from central_v2.backend.routes.router import dispatch_get, dispatch_post


class CentralV2MergeManualTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.manga = self.root / "comix" / "Synthetic"
        self.chapter = self.manga / "IMG" / "6"
        self.chapter.mkdir(parents=True)
        Image.new("RGB", (12, 80), "white").save(self.chapter / "page-001.png")
        stage = self.manga / "FLUXO_SECUNDARIO/01_MERGE_PROCESSAMENTO/MERGE_LEVEL5/6"
        stage.mkdir(parents=True)
        level4 = self.manga / "FLUXO_SECUNDARIO/01_MERGE_PROCESSAMENTO/MERGE_LEVEL4/6"
        level4.mkdir(parents=True)
        level4_path = level4 / "merge-level4-manifest.json"
        level4_path.write_text("{}", encoding="utf-8")
        (stage / "merge-level5-manifest.json").write_text(json.dumps({
            "schema_version": 1,
            "algorithm": "merge_level5_global_structural_safe_v1",
            "chapter": "6",
            "total_height": 80,
            "source_level4_sha256": hashlib.sha256(level4_path.read_bytes()).hexdigest(),
            "residual_pending_segments": [{"global_start": 20, "global_end": 80}],
        }), encoding="utf-8")

    def tearDown(self):
        self.temporary.cleanup()

    def test_state_lists_only_review_residuals_and_maps_source_pages(self):
        response = dispatch_get("/api/merge-manual?provider=comix&manga=Synthetic", self.root)
        payload = json.loads(response.body)
        self.assertEqual(response.status, 200)
        self.assertEqual(payload["summary"]["pending"], 1)
        block = payload["chapters"][0]["pending_blocks"][0]
        self.assertEqual((block["global_start"], block["global_end"]), (20, 80))
        self.assertEqual(block["pages"][0]["file"], "page-001.png")

    def test_preview_endpoint_serves_only_image_in_selected_chapter(self):
        response = dispatch_get(
            "/api/merge-manual/image?provider=comix&manga=Synthetic&chapter=6&file=page-001.png",
            self.root,
        )
        self.assertEqual(response.status, 200)
        self.assertEqual(response.content_type, "image/png")
        denied = dispatch_get(
            "/api/merge-manual/image?provider=comix&manga=Synthetic&chapter=../6&file=page-001.png",
            self.root,
        )
        self.assertEqual(denied.status, 404)

    def test_proposal_endpoint_uses_selected_range_and_persists_cut_manifest(self):
        response = dispatch_post("/api/merge-manual/proposal", {
            "provider": "comix", "manga": "Synthetic", "chapter": "6",
            "block_id": "pending-1", "start": "page-001.png", "end": "page-001.png",
            "cuts": [30],
        }, self.root)
        payload = json.loads(response.body)
        self.assertEqual(response.status, 201)
        self.assertEqual(payload["status"], "PROPOSTA_GERADA")
        self.assertEqual(payload["cuts"], [30])
        proposal_dir = self.manga / "FLUXO_SECUNDARIO/01_MERGE_PROCESSAMENTO/MERGE_MANUAL_PROPOSALS/6" / payload["proposal_id"]
        self.assertTrue((proposal_dir / "merge-manual-manifest.json").is_file())


if __name__ == "__main__":
    unittest.main()
