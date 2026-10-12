"""One-use laboratory approvals stay bound to their source, ROIs and report."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from central_v2.backend.orchestration.textoff_special.artifacts import read_json, sha256, write_json
from central_v2.backend.orchestration.textoff_special.lab_degrade_authorization import (
    candidate_rows, consume, issue, load_pending,
)


class LaboratoryDegradeAuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        write_json(self.folder / "manifest.json", {"run_id": "1" * 32,
                   "execution_status": "failed"})
        self.report = self.folder / "report.json"
        self.mask = self.folder / "mask.png"
        self.report.write_text(json.dumps({"pages": [{"source": "source.png",
            "component_decisions": [
                {"component": 2, "bbox": [10, 10, 20, 20], "area": 180,
                 "reason": "transparent_balloon_deferred"},
                {"component": 3, "bbox": [45, 10, 20, 20], "area": 170,
                 "reason": "transparent_balloon_deferred"},
                {"component": 4, "bbox": [90, 10, 20, 20], "area": 160,
                 "reason": "outside_or_ambiguous"},
            ]}]}), encoding="utf-8")
        self.mask.write_bytes(b"raw candidate mask")
        self.request = {"source": {"path": "/input/source.png", "sha256": "a" * 64,
                                  "chapter": "chapter", "filename": "page.png"},
                        "selections": [{"x": 0, "y": 0, "width": 70, "height": 40}]}
        self.candidates, self.binding = candidate_rows(self.request, self.report, self.mask)

    def test_lists_only_intersecting_deferred_components_and_allows_multiple_selection(self):
        self.assertEqual([item["component"] for item in self.candidates], [2, 3])
        token, record = issue(self.folder, "1" * 32, self.request,
                              self.candidates, self.binding)
        manifest = read_json(self.folder / "manifest.json")
        self.assertEqual(manifest["laboratory_authorization_proposal"]["status"], "pending")
        self.assertFalse((self.folder / "laboratory-authorization.json").exists())
        authorization = consume(self.folder, record,
                                [self.candidates[0]["id"], self.candidates[1]["id"]])
        self.assertEqual(len(authorization["components"]), 2)
        with self.assertRaisesRegex(ValueError, "consumida"):
            load_pending(self.folder, token)

    def test_expired_proposal_is_rejected(self):
        write_json(self.folder / "manifest.json", {"run_id": "2" * 32})
        token, record = issue(self.folder, "2" * 32, self.request,
                              self.candidates, self.binding)
        record["expires_at"] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        manifest = read_json(self.folder / "manifest.json")
        manifest["laboratory_authorization_proposal"] = record
        write_json(self.folder / "manifest.json", manifest)
        with self.assertRaisesRegex(ValueError, "expirada"):
            load_pending(self.folder, token)
        self.assertEqual(read_json(self.folder / "manifest.json")
                         ["laboratory_authorization_proposal"]["status"], "expired")

    def test_source_roi_report_and_mask_changes_change_the_binding(self):
        changed_source = {**self.request, "source": {**self.request["source"],
                                                       "sha256": "b" * 64}}
        changed_roi = {**self.request, "selections": [
            {"x": 1, "y": 0, "width": 69, "height": 40}]}
        source_rows, source_binding = candidate_rows(changed_source, self.report, self.mask)
        roi_rows, roi_binding = candidate_rows(changed_roi, self.report, self.mask)
        self.assertNotEqual(source_binding, self.binding)
        self.assertNotEqual(roi_binding, self.binding)
        self.assertNotEqual(source_rows[0]["id"], self.candidates[0]["id"])
        self.assertNotEqual(roi_rows[0]["id"], self.candidates[0]["id"])
        old_binding = self.binding.copy()
        self.report.write_text(self.report.read_text(encoding="utf-8") + " ", encoding="utf-8")
        _, report_binding = candidate_rows(self.request, self.report, self.mask)
        self.assertNotEqual(report_binding, old_binding)
        old_binding = report_binding
        self.mask.write_bytes(b"changed raw candidate mask")
        _, mask_binding = candidate_rows(self.request, self.report, self.mask)
        self.assertNotEqual(mask_binding, old_binding)

    def test_confirmation_must_select_current_candidate_ids(self):
        write_json(self.folder / "manifest.json", {"run_id": "3" * 32})
        _, record = issue(self.folder, "3" * 32, self.request,
                          self.candidates, self.binding)
        with self.assertRaisesRegex(ValueError, "presentes"):
            consume(self.folder, record, ["not-a-candidate"])


if __name__ == "__main__":
    unittest.main()
