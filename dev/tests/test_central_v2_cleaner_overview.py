"""Cleaner indicators preserve stage identity and current preview provenance."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from central_v2.backend.orchestration.textoff_merged import overview


class CleanerOverviewTests(unittest.TestCase):
    def test_stage_identity_and_level1_selection(self):
        rows = [{"chapter": "1", "cleaned": True, "merge_valid": True,
                 "level2_status": "no_change", "selectable": False}]
        with patch.object(overview, "query_merged_level2", return_value={"chapters": rows}), \
             patch.object(overview, "query_level3", return_value={"chapters": [
                 {"chapter": "1", "cleaned": False}]}), \
             patch.object(overview, "current_previews", return_value={"1": {"ac4", "artistic"}}):
            row = overview.query_cleaner_overview(Path("/manga"))["chapters"][0]
        self.assertEqual(row["stages"], dict(ac1=True, ac2=True, ac3=False, ac4=True, map=False))
        self.assertEqual(row["retouch"], dict(degrade=False, artistic=True, soft=False))
        self.assertTrue(row["selectable"])

    def test_failed_foreign_and_obsolete_previews_are_excluded(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            manga = root / "manga"
            source = {"manga": str(manga), "chapter": "1", "level": "MERGED_NIVEL_I",
                      "filename": "page.png", "sha256": "input", "predecessors": []}
            base = {"source": source, "execution_status": "succeeded", "treatment": "degrade",
                    "result_file": "result.png", "validation": {"result_sha256": "output"}}
            for name, changes in [("valid", {}), ("failed", {"execution_status": "failed"}),
                                  ("foreign", {"source": {**source, "manga": "/other"}}),
                                  ("stale", {"source": {**source, "predecessors": ["old"]}})]:
                folder = root / name
                folder.mkdir()
                (folder / "manifest.json").write_text(json.dumps({**base, **changes}))
                (folder / "result.png").write_bytes(b"result")
            with patch.object(overview, "resolve_input", return_value={"predecessors": []}) as resolve, \
                 patch.object(overview, "sha256", return_value="output"):
                self.assertEqual(overview.current_previews(manga, root), {"1": {"degrade"}})
                self.assertEqual(resolve.call_count, 2)
