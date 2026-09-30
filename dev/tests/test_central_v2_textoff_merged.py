import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from central_v2.backend.routes.router import dispatch_get, dispatch_post


class CentralV2TextoffMergedRouteTests(unittest.TestCase):
    def make_output(self, root):
        output = Path(root)
        (output / "ridi" / "obra" / "IMG" / "3").mkdir(parents=True)
        return output

    def test_query_exposes_merge_worklist_for_selected_obra(self):
        with tempfile.TemporaryDirectory() as root:
            output = self.make_output(root)
            response = dispatch_get("/api/textoff/merged?provider=ridi&manga=obra", output)
        self.assertEqual(response.status, 200)
        payload = json.loads(response.body)
        self.assertEqual(payload["manga"], "obra")
        self.assertEqual(payload["chapters"][0]["chapter"], "3")
        self.assertFalse(payload["chapters"][0]["selectable"])

    def test_explicit_level2_query_reports_missing_level1_separately(self):
        with tempfile.TemporaryDirectory() as root:
            output = self.make_output(root)
            response = dispatch_get("/api/textoff/merged/level2?provider=ridi&manga=obra", output)
        self.assertEqual(response.status, 200)
        payload = json.loads(response.body)
        self.assertEqual(payload["chapters"][0]["level2_status"], "invalid_merge")
        self.assertFalse(payload["chapters"][0]["selectable"])

    def test_level_three_is_listed_for_level_one_candidates(self):
        with tempfile.TemporaryDirectory() as root:
            output = self.make_output(root)
            response = dispatch_get(
                "/api/textoff/merged/level3?provider=ridi&manga=obra", output)
            self.assertEqual(response.status, 200)
            row = json.loads(response.body)["chapters"][0]
            self.assertEqual(row["level3_status"], "missing_level1")
            self.assertFalse(row["selectable"])

    def test_level3_image_serves_only_pages_referenced_by_completed_report(self):
        with tempfile.TemporaryDirectory() as root:
            output = self.make_output(root)
            image_dir = output / "ridi/obra/FLUXO_SECUNDARIO/04_TEXTO_OFF/TO_MERGED_NIVEL_I/3/clean"
            image_dir.mkdir(parents=True)
            image = image_dir / "page-001-001_clean.png"
            image.write_bytes(b"merge-image")
            consolidated = output / "ridi/obra/FLUXO_SECUNDARIO/04_TEXTO_OFF/TO_MERGED_CONSOLIDADO/3/json"
            consolidated.mkdir(parents=True)
            (consolidated / "clean-manifest.json").write_text(json.dumps({"selections": [{
                "artifact": "clean/page-001-001_clean.png", "source": "page-001-001.png",
                "selected_from": "TO_MERGED_NIVEL_I", "sha256": hashlib.sha256(b"merge-image").hexdigest(),
            }]}), encoding="utf-8")
            row = {"chapter": "3", "cleaned": True,
                   "candidate_pages": [{"source": image.name, "candidates": [{
                       "bbox": [1, 2, 3, 4], "candidate_type": "irregular_outline"}]}]}
            with patch("central_v2.backend.routes.textoff_merged.query_level3",
                       return_value={"chapters": [row]}):
                response = dispatch_get(
                    "/api/textoff/merged/level3/image?provider=ridi&manga=obra&chapter=3&file=page-001-001_clean.png",
                    output,
                )
                rejected = dispatch_get(
                    "/api/textoff/merged/level3/image?provider=ridi&manga=obra&chapter=3&file=secret.png",
                    output,
                )
        self.assertEqual(response.status, 200)
        self.assertEqual(response.body, b"merge-image")
        self.assertEqual(response.content_type, "image/png")
        self.assertEqual(rejected.status, 404)

    def test_levels_four_and_five_are_listed_only_from_level_one_readiness(self):
        with tempfile.TemporaryDirectory() as root:
            output = self.make_output(root)
            for level in ("IV", "V"):
                response = dispatch_get(
                    f"/api/textoff/merged/level{level}?provider=ridi&manga=obra", output)
                payload = json.loads(response.body)
                row = payload["chapters"][0]
                self.assertEqual(response.status, 200)
                self.assertFalse(row["level1_ready"])
                self.assertFalse(row["selectable"])
                self.assertEqual(row["special_level"], level)

    def test_execute_enqueues_v2_job_for_validated_selection(self):
        with tempfile.TemporaryDirectory() as root:
            output = self.make_output(root)
            with patch("central_v2.backend.routes.textoff_merged.validate_selection", return_value=["3"]), \
                 patch("central_v2.backend.routes.textoff_merged.legacy_server_active", return_value=False), \
                 patch("central_v2.backend.routes.textoff_merged.submit", return_value={"id": "job-merged"}) as submit:
                response = dispatch_post("/api/textoff/merged/execute", {
                    "provider": "ridi", "manga": "obra", "chapters": ["3"],
                }, output)
        self.assertEqual(response.status, 202)
        self.assertEqual(json.loads(response.body)["job"]["id"], "job-merged")
        self.assertEqual(submit.call_args.kwargs["total"], 1)

    def test_level3_execution_requires_level1_ready_chapter(self):
        with tempfile.TemporaryDirectory() as root:
            output = self.make_output(root)
            with patch("central_v2.backend.routes.textoff_merged.validate_selection", return_value=["3"]), \
                 patch("central_v2.backend.routes.textoff_merged.legacy_server_active", return_value=False), \
                 patch("central_v2.backend.routes.textoff_merged.submit", return_value={"id": "job-level3"}), \
                 patch("central_v2.backend.routes.textoff_merged.query_level3", return_value={
                     "chapters": [{"chapter": "3", "selectable": True}]}):
                response = dispatch_post("/api/textoff/merged/level3/execute", {
                    "provider": "ridi", "manga": "obra", "chapters": ["3"],
                }, output)
        self.assertEqual(response.status, 202)

    def test_level3_execution_rejects_chapter_without_level1(self):
        with tempfile.TemporaryDirectory() as root:
            output = self.make_output(root)
            with patch("central_v2.backend.routes.textoff_merged.validate_selection", return_value=["3"]), \
                 patch("central_v2.backend.routes.textoff_merged.legacy_server_active", return_value=False), \
                 patch("central_v2.backend.routes.textoff_merged.query_level3", return_value={
                     "chapters": [{"chapter": "3", "selectable": False}]}):
                response = dispatch_post("/api/textoff/merged/level3/execute", {
                    "provider": "ridi", "manga": "obra", "chapters": ["3"],
                }, output)
        self.assertEqual(response.status, 400)


if __name__ == "__main__":
    unittest.main()
