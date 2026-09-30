"""Worklist outcomes require results for all expected pages."""
from pathlib import Path
import unittest
from unittest.mock import patch

from central_v2.backend.orchestration.textoff_merged import special_status


class SpecialStatusTests(unittest.TestCase):
    def project(self, previews, ready=True):
        row = {"chapter": "1", "level1_ready": ready,
               "transparent_pages": ["01.png", "02.png"]}
        with patch.object(special_status, "query_special_level", return_value={"chapters": [row]}), \
             patch.object(special_status, "current_preview_records", return_value=previews):
            return special_status.query_special_worklist(Path("/manga"), "IV")["chapters"][0]

    def preview(self, filename, pixels=0, date="2026-01-01", stage="ac3"):
        return stage, {"source": {"chapter": "1", "filename": filename},
                       "validation": {"changed_pixels": pixels}, "finished_at": date}

    def test_partial_and_other_stage_do_not_complete(self):
        self.assertEqual(self.project([self.preview("01_clean.png")])["cleaner_status"], "pending")
        self.assertEqual(self.project([self.preview("01_clean.png", stage="ac4")])["cleaner_status"], "pending")
        self.assertEqual(self.project([], ready=False)["cleaner_status"], "missing_level1")

    def test_latest_page_results_determine_unchanged(self):
        previews = [self.preview("01_clean.png", 20), self.preview("02_clean.png")]
        self.assertEqual(self.project(previews)["cleaner_status"], "processed")
        previews.append(self.preview("01_clean.png", 0, "2026-01-02"))
        self.assertEqual(self.project(previews)["cleaner_status"], "no_change")
