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

    def test_levels_four_and_five_are_listed_only_from_level_one_readiness(self):
        with tempfile.TemporaryDirectory() as root:
            output = self.make_output(root)
            self.assertIsNone(dispatch_get(
                "/api/textoff/merged/levelIII?provider=ridi&manga=obra", output))
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


if __name__ == "__main__":
    unittest.main()
