import tempfile
import unittest
from pathlib import Path

from processamento.unificacao_imagens import image_stitcher as stitcher


class MergePageRangeNamingContractTests(unittest.TestCase):
    def test_single_page_name(self):
        self.assertEqual(
            stitcher.page_range_output_name("page-068.png", "page-068.png"),
            "page-068.png",
        )

    def test_multi_page_name(self):
        self.assertEqual(
            stitcher.page_range_output_name("page-068.png", "page-073.png"),
            "page-068-073.png",
        )

    def test_source_extension_does_not_change_output_contract(self):
        self.assertEqual(
            stitcher.page_range_output_name("page-001.webp", "page-012.img"),
            "page-001-012.png",
        )

    def test_spans_use_only_pages_intersecting_output_interval(self):
        spans = [
            {"file": "page-068.png", "global_start": 0, "global_end": 100},
            {"file": "page-069.png", "global_start": 100, "global_end": 200},
            {"file": "page-070.png", "global_start": 200, "global_end": 300},
        ]
        self.assertEqual(
            stitcher.page_range_output_name_from_spans(spans, 100, 300),
            "page-069-070.png",
        )

    def test_collision_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            (d / "page-001-003.png").write_bytes(b"x")
            with self.assertRaises(ValueError):
                stitcher.ensure_unique_output_path(d, "page-001-003.png")

    def test_reader_accepts_new_and_legacy_during_transition(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            for name in ("page-001-003.png", "merged-002.png", "ignore.png"):
                (d / name).write_bytes(b"x")
            names = [p.name for p in stitcher.merge_artifact_files(d)]
            self.assertIn("page-001-003.png", names)
            self.assertIn("merged-002.png", names)
            self.assertNotIn("ignore.png", names)


if __name__ == "__main__":
    unittest.main()
