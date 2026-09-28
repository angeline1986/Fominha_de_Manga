import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

from processamento.unificacao_imagens.image_stitcher_level2 import (
    Level2Config,
    analyze_uniform_color_bands,
    solve_pending_region,
)


@dataclass(frozen=True)
class Candidate:
    start: int
    end: int
    height: int
    white_ratio_mean: float = 1.0


def white_band(center: int, width: int = 160) -> Candidate:
    return Candidate(center - width // 2, center + width // 2, width)


class AutoMergeLevel2CharacterizationTests(unittest.TestCase):
    def setUp(self):
        self.config = Level2Config(
            target_height=60,
            min_chunk_height=30,
            max_chunk_height=100,
            min_white_band=10,
            min_uniform_band=10,
        )

    def test_short_residual_is_resolved_without_inventing_a_cut(self):
        result = solve_pending_region(10, 90, [], self.config)
        self.assertEqual(result["status"], "resolved")
        self.assertEqual(result["resolved_intervals"], [[10, 90]])
        self.assertEqual(result["selected_cuts"], [])

    def test_safe_path_prefers_bounded_balanced_intervals(self):
        result = solve_pending_region(
            0, 160, [white_band(60), white_band(120)], self.config,
        )
        self.assertEqual(result["status"], "resolved")
        self.assertEqual(result["resolved_intervals"], [[0, 60], [60, 120], [120, 160]])
        self.assertTrue(all(30 <= end - start <= 100 for start, end in result["resolved_intervals"]))

    def test_partial_path_preserves_unresolved_suffix(self):
        result = solve_pending_region(
            0, 230, [white_band(60), white_band(120)], self.config,
        )
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["resolved_intervals"], [[0, 60], [60, 120]])
        self.assertEqual(result["residual_interval"], [120, 230])

    def test_no_safe_path_preserves_whole_residual(self):
        result = solve_pending_region(0, 250, [], self.config)
        self.assertEqual(result["status"], "unresolved")
        self.assertEqual(result["resolved_intervals"], [])
        self.assertEqual(result["residual_interval"], [0, 250])

    def test_small_edge_chunk_is_allowed_only_at_real_residual_edge(self):
        config = Level2Config(
            target_height=90,
            min_chunk_height=70,
            max_chunk_height=100,
            min_white_band=10,
            min_uniform_band=10,
        )
        result = solve_pending_region(0, 130, [white_band(50)], config)
        self.assertEqual(result["status"], "resolved")
        self.assertTrue(result["edge_chunk_relaxation_used"])
        self.assertEqual(
            [(item["position"], item["global_start"], item["global_end"]) for item in result["edge_chunks"]],
            [("start", 0, 50)],
        )
        self.assertFalse(any(item["position"] == "internal" for item in result["edge_chunks"]))

    def test_uniform_band_detection_accepts_nonwhite_flat_color(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "page-001.png"
            pixels = np.full((80, 24, 3), (80, 110, 140), dtype=np.uint8)
            pixels[30:50] = (220, 20, 20)
            Image.fromarray(pixels).save(path)
            bands = analyze_uniform_color_bands(
                [path], sample_width=24, max_channel_std=4, max_row_delta=3,
            )
        self.assertTrue(any((item.start, item.end) == (0, 30) for item in bands))
        self.assertTrue(any((item.start, item.end) == (51, 80) for item in bands))
        self.assertFalse(any(item.start < 30 and item.end > 50 for item in bands))

    def test_source_file_preference_does_not_override_safe_maximum(self):
        result = solve_pending_region(
            0, 225, [white_band(60), white_band(110)], self.config,
            source_intervals=[(0, 10), (10, 20), (20, 30), (30, 40)],
        )
        self.assertEqual(result["status"], "partial")
        self.assertTrue(result["balance"]["preference_is_not_safety_rule"])
        self.assertLessEqual(max(item["height"] for item in result["balance"]["chunks"]), 100)


if __name__ == "__main__":
    unittest.main()
