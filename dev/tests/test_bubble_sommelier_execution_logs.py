import json
import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import patch

from central_v2.backend.orchestration.bubble_sommelier import execution


class BubbleSommelierExecutionLogTests(unittest.TestCase):
    def test_page_callback_keeps_structured_progress_and_compact_messages(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            report = root / "report.json"
            payload = {"checkpoints": {"result": {
                "pages": 1, "crops": 2, "coverageGe075": 1, "candidates": 1,
            }}}
            events = []

            def fake_run(_source, _output, _profile, *, on_progress, progress_context):
                on_progress({"type": "run_started", "total_pages": 1})
                on_progress({"type": "page_started", "current": 1, "total": 1,
                             "page_id": "page-001.png"})
                on_progress({"type": "page_completed", "current": 1, "total": 1,
                             "page_id": "page-001.png", "percent": 100,
                             "raw_detections": 4, "bubbles": 2, "candidates": 1})
                report.write_text(json.dumps(payload), encoding="utf-8")

            with patch.object(execution, "validate_profile_id", return_value="poc_a_v1"), \
                 patch.object(execution, "merge_dir", return_value=root), \
                 patch.object(execution, "execution_dir", return_value=root), \
                 patch.object(execution, "report_path", return_value=report), \
                 patch.object(execution, "replace_execution_artifacts", return_value=nullcontext()), \
                 patch.object(execution, "run", side_effect=fake_run), \
                 patch.object(execution, "validate_report", side_effect=lambda value, _profile: value):
                execution.execute(root / "manga", ["1"],
                                  lambda chapter, progress: events.append((chapter, progress)),
                                  "poc_a_v1", provider="comix", manga_name="Manga")

        page_events = [value for _, value in events if value.get("stage") == "page"]
        self.assertEqual(len(page_events), 1)
        self.assertEqual(page_events[0]["percent"], 100)
        self.assertEqual(page_events[0]["bubbles"], 2)
        self.assertEqual(page_events[0]["candidates"], 1)
        self.assertGreaterEqual(page_events[0]["duration"], 0)
        self.assertNotIn("100%", page_events[0]["message"])
        self.assertNotIn("\n", page_events[0]["message"])


if __name__ == "__main__":
    unittest.main()
