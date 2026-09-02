import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from interface_web import processing_web as pw


class Level3ReviewItemsTests(unittest.TestCase):
    def make_review_case(self, root):
        manga = Path(root) / "manga"
        ch = manga / "IMG" / "6"
        ch.mkdir(parents=True)
        Image.new("RGB", (8, 100), (255, 255, 255)).save(
            ch / "page-001.png"
        )

        review_dir = Path(root) / "review"
        review_dir.mkdir(parents=True)
        Image.new("RGB", (8, 50), (255, 0, 0)).save(
            review_dir / "merged-001.png"
        )
        Image.new("RGB", (8, 50), (0, 0, 255)).save(
            review_dir / "merged-002.png"
        )
        payload = {
            "boundaries": [0, 50, 100],
            "source_pages": ["page-001.png"],
            "policy": {"max_source_images": 8},
            "cuts": [],
            "proposal": [],
        }
        (review_dir / "merge-review.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        failure = {
            "level2_status": "validated",
            "partition": {
                "level2_validated": True,
                "total_height": 100,
                "pending_segments": [
                    {"global_start": 0, "global_end": 100}
                ],
            },
        }
        return manga, ch, review_dir, failure

    def test_review_items_use_only_level3_residual(self):
        with tempfile.TemporaryDirectory() as td:
            manga, ch, review_dir, failure = self.make_review_case(td)
            residual = [{"global_start": 50, "global_end": 100}]
            with patch.object(pw, "rdir", return_value=review_dir), \
                 patch.object(pw, "read_merge_failure", return_value=failure), \
                 patch.object(
                     pw,
                     "_level3_review_pending",
                     return_value=(residual, None, "level3"),
                 ):
                items = pw.review_merge_items(manga, ch)

            self.assertEqual(len(items), 1)
            self.assertEqual(items[0]["global_start"], 50)
            self.assertEqual(items[0]["global_end"], 100)
            self.assertIn(
                "auto_merge_pending_interval",
                items[0]["review_reasons"],
            )

    def test_review_items_fail_closed_on_invalid_level3(self):
        with tempfile.TemporaryDirectory() as td:
            manga, ch, review_dir, failure = self.make_review_case(td)
            with patch.object(pw, "rdir", return_value=review_dir), \
                 patch.object(pw, "read_merge_failure", return_value=failure), \
                 patch.object(
                     pw,
                     "_level3_review_pending",
                     return_value=(None, "Level III stale", "level3"),
                 ):
                items = pw.review_merge_items(manga, ch)

            self.assertEqual(items, [])

    def test_review_items_are_empty_when_level3_has_no_residual(self):
        with tempfile.TemporaryDirectory() as td:
            manga, ch, review_dir, failure = self.make_review_case(td)
            with patch.object(pw, "rdir", return_value=review_dir), \
                 patch.object(pw, "read_merge_failure", return_value=failure), \
                 patch.object(
                     pw,
                     "_level3_review_pending",
                     return_value=(None, None, "level3"),
                 ):
                items = pw.review_merge_items(manga, ch)

            self.assertEqual(items, [])


if __name__ == "__main__":
    unittest.main()
