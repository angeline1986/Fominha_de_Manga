from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from processamento.merge_manual.review_state import build_pending_blocks, state_from_review_row, validate_page_range
from processamento.merge_manual.service import build_read_state


class MergeManualReadonlyTests(unittest.TestCase):
    def make_chapter(self):
        tmp = tempfile.TemporaryDirectory()
        manga = Path(tmp.name)
        chapter = manga / "IMG" / "6"
        chapter.mkdir(parents=True)
        for name, height in (("page-001.png", 100), ("page-002.png", 120), ("page-003.png", 80)):
            Image.new("RGB", (50, height), "white").save(chapter / name)
        return tmp, manga, chapter

    def test_build_pending_blocks_maps_global_axis_to_pages(self):
        tmp, _, chapter = self.make_chapter()
        self.addCleanup(tmp.cleanup)
        blocks = build_pending_blocks(chapter, [{"global_start": 90, "global_end": 250}])
        self.assertEqual([p["file"] for p in blocks[0]["pages"]], ["page-001.png", "page-002.png", "page-003.png"])
        self.assertEqual(blocks[0]["pages"][0]["source_y_start"], 90)
        self.assertEqual(blocks[0]["pages"][-1]["source_y_end"], 30)

    def test_validate_range_requires_same_block_and_natural_order(self):
        tmp, _, chapter = self.make_chapter()
        self.addCleanup(tmp.cleanup)
        block = build_pending_blocks(chapter, [{"global_start": 100, "global_end": 300}])[0]
        selected = validate_page_range(block, "page-002.png", "page-003.png")
        self.assertEqual(selected["global_start"], 100)
        self.assertEqual(selected["global_end"], 300)
        with self.assertRaisesRegex(ValueError, "Fim"):
            validate_page_range(block, "page-003.png", "page-002.png")

    def test_state_is_read_from_same_review_row_level5(self):
        current = state_from_review_row({
            "needs_review": True,
            "merge_state": "pendente_review",
            "merge_level5_detail": {
                "available": True,
                "valid": True,
                "review_pending_segments": [{"global_start": 100, "global_end": 300}],
            },
        })
        self.assertTrue(current["eligible"])
        self.assertEqual(current["status"], "pending")
        self.assertEqual(current["source"], "level5")
        self.assertEqual(len(current["pending_segments"]), 1)

    def test_outside_review_is_not_listed(self):
        tmp, manga, chapter = self.make_chapter()
        self.addCleanup(tmp.cleanup)
        state = build_read_state(
            manga,
            [chapter],
            review_state_loader=lambda _: {"needs_review": False, "merge_state": "novo"},
        )
        self.assertEqual(state["chapters"], [])

    def test_service_lists_pending_review_chapter(self):
        tmp, manga, chapter = self.make_chapter()
        self.addCleanup(tmp.cleanup)
        state = build_read_state(
            manga,
            [chapter],
            review_state_loader=lambda _: {
                "needs_review": True,
                "merge_state": "pendente_review",
                "merge_level5_detail": {
                    "available": True,
                    "valid": True,
                    "review_pending_segments": [{"global_start": 100, "global_end": 300}],
                },
            },
        )
        self.assertEqual(state["schema_version"], 2)
        self.assertEqual(state["source_of_truth"], "review_row_state")
        self.assertEqual(state["summary"]["pending"], 1)
        self.assertEqual(state["chapters"][0]["chapter"], "6")
        self.assertEqual(state["chapters"][0]["pending_pages"], 2)


if __name__ == "__main__":
    unittest.main()
