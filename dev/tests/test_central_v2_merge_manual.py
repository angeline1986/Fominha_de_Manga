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

    def test_state_marks_applied_manual_range_and_removes_it_from_pending(self):
        proposal_id = "manual-test"
        proposal_dir = self.manga / "FLUXO_SECUNDARIO/01_MERGE_PROCESSAMENTO/MERGE_MANUAL_PROPOSALS/6" / proposal_id
        proposal_dir.mkdir(parents=True)
        (proposal_dir / "merge-manual-manifest.json").write_text(json.dumps({
            "proposal_id": proposal_id,
            "chapter": "6",
            "status": "EFETIVADO",
        }), encoding="utf-8")
        official = self.manga / "FLUXO_SECUNDARIO/02_MERGE/6"
        official.mkdir(parents=True)
        Image.new("RGB", (12, 80), "white").save(official / "page-001.png")
        (official / "merge-manifest.json").write_text(json.dumps({
            "merged_images": 1,
            "source_total_height": 80,
            "outputs": [{
                "file": "page-001.png",
                "global_start": 0,
                "global_end": 80,
                "width": 12,
                "height": 80,
            }],
            "composition": {
                "manual_proposal_id": proposal_id,
                "manual_range": [20, 80],
            },
        }), encoding="utf-8")

        response = dispatch_get("/api/merge-manual?provider=comix&manga=Synthetic", self.root)
        payload = json.loads(response.body)
        row = payload["chapters"][0]
        self.assertEqual(response.status, 200)
        self.assertEqual(row["status"], "resolved")
        self.assertTrue(row["manual_range_applied"])
        self.assertEqual(row["pending_pages"], 0)
        self.assertEqual(row["pending_blocks"], [])
        self.assertEqual(payload["summary"]["pending"], 0)
        self.assertEqual(payload["summary"]["resolved"], 1)

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

    def test_saved_proposals_lists_generated_and_applied_without_mutating_them(self):
        proposals = self.manga / "FLUXO_SECUNDARIO/01_MERGE_PROCESSAMENTO/MERGE_MANUAL_PROPOSALS/6"
        for proposal_id, status in (("pending-1", "PROPOSTA_GERADA"), ("applied-1", "EFETIVADO")):
            folder = proposals / proposal_id
            folder.mkdir(parents=True)
            (folder / "merge-manual-manifest.json").write_text(json.dumps({
                "proposal_id": proposal_id, "chapter": "6", "status": status,
                "source_block": {"start": "page-001.png", "end": "page-001.png"},
                "outputs": [{"file": "block-001.png"}],
            }), encoding="utf-8")
        before = {path: path.read_bytes() for path in proposals.glob("*/merge-manual-manifest.json")}
        response = dispatch_get("/api/merge-manual/proposals?provider=comix&manga=Synthetic", self.root)
        payload = json.loads(response.body)
        self.assertEqual(response.status, 200)
        self.assertCountEqual([item["status"] for item in payload["proposals"]], ["PROPOSTA_GERADA", "EFETIVADO"])
        self.assertEqual(before, {path: path.read_bytes() for path in before})

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

    def test_proposal_image_endpoint_serves_only_declared_output_files(self):
        response = dispatch_post("/api/merge-manual/proposal", {
            "provider": "comix", "manga": "Synthetic", "chapter": "6",
            "block_id": "pending-1", "start": "page-001.png", "end": "page-001.png",
            "cuts": [30],
        }, self.root)
        proposal = json.loads(response.body)
        output = proposal["outputs"][0]["file"]
        image = dispatch_get(
            f"/api/merge-manual/proposal/image?provider=comix&manga=Synthetic&chapter=6&proposal_id={proposal['proposal_id']}&file={output}",
            self.root,
        )
        denied = dispatch_get(
            f"/api/merge-manual/proposal/image?provider=comix&manga=Synthetic&chapter=6&proposal_id={proposal['proposal_id']}&file=private.png",
            self.root,
        )
        self.assertEqual((image.status, image.content_type), (200, "image/png"))
        self.assertEqual(denied.status, 404)


if __name__ == "__main__":
    unittest.main()
