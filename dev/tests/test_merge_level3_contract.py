#!/usr/bin/env python3
import unittest

import cv2
import numpy as np

from processamento.unificacao_imagens.image_stitcher_level3 import (
    Level3Config,
    Level3Decision,
    Level3PendingRegion,
    Level3Result,
    analyze_structural_candidate,
    normalize_pending_segments,
    placeholder_structural_evaluation,
    preprocess_for_structure,
)


class Level3ContractTests(unittest.TestCase):
    def test_decision_values_are_stable(self):
        self.assertEqual(Level3Decision.SAFE.value, "SAFE")
        self.assertEqual(Level3Decision.UNSAFE.value, "UNSAFE")
        self.assertEqual(Level3Decision.INCONCLUSIVE.value, "INCONCLUSIVE")

    def test_normalize_pending_segments_orders_without_mutating_bounds(self):
        regions = normalize_pending_segments(
            [
                {"global_start": 500, "global_end": 900},
                {"global_start": 100, "global_end": 300},
            ],
            total_height=1000,
        )
        self.assertEqual(
            [(x.global_start, x.global_end) for x in regions],
            [(100, 300), (500, 900)],
        )

    def test_normalize_rejects_overlap(self):
        with self.assertRaises(ValueError):
            normalize_pending_segments(
                [
                    {"global_start": 100, "global_end": 500},
                    {"global_start": 400, "global_end": 700},
                ],
                total_height=1000,
            )

    def test_normalize_rejects_out_of_coverage(self):
        with self.assertRaises(ValueError):
            normalize_pending_segments(
                [{"global_start": 100, "global_end": 1100}],
                total_height=1000,
            )

    def test_placeholder_is_fail_closed(self):
        region = Level3PendingRegion(100, 500)
        result = placeholder_structural_evaluation(
            candidate_y=250,
            region=region,
        )
        self.assertEqual(result.decision, Level3Decision.INCONCLUSIVE)
        self.assertEqual(
            result.reason,
            "structural_analysis_not_implemented",
        )
        self.assertIsNone(result.alternative_y)

    def test_placeholder_rejects_candidate_outside_pending_region(self):
        region = Level3PendingRegion(100, 500)
        with self.assertRaises(ValueError):
            placeholder_structural_evaluation(
                candidate_y=500,
                region=region,
            )

    def test_result_is_auditable_dict(self):
        result = Level3Result(
            decision=Level3Decision.UNSAFE,
            candidate_y=250,
            reason="example_reason",
            region_start=100,
            region_end=500,
            metrics={"edge_density": 0.12},
            alternative_y=220,
        )
        self.assertEqual(result.as_dict()["decision"], "UNSAFE")
        self.assertEqual(result.as_dict()["alternative_y"], 220)


class Level3AntiSliceTests(unittest.TestCase):
    def setUp(self):
        self.region = Level3PendingRegion(0, 400)
        self.cfg = Level3Config(
            analysis_half_window=100,
            min_component_area=20,
            min_component_height=8,
            hough_threshold=12,
            hough_min_line_length=20,
            hough_max_line_gap=4,
        )

    def test_preprocess_reduces_screentone_noise(self):
        img = np.full((200, 240), 230, dtype=np.uint8)
        img[::4, ::4] = 80

        raw_edges = cv2.Canny(img, 50, 150)
        _, denoised_edges = preprocess_for_structure(img, config=self.cfg)

        self.assertLess(
            np.count_nonzero(denoised_edges),
            np.count_nonzero(raw_edges),
        )

    def test_uniform_white_band_is_safe(self):
        img = np.full((300, 240), 255, dtype=np.uint8)
        result = analyze_structural_candidate(
            img,
            candidate_y=150,
            region=self.region,
            config=self.cfg,
        )
        self.assertEqual(result.decision, Level3Decision.SAFE)
        self.assertEqual(result.reason, "structurally_clear_uniform_band")

    def test_uniform_black_band_is_safe(self):
        img = np.zeros((300, 240), dtype=np.uint8)
        result = analyze_structural_candidate(
            img,
            candidate_y=150,
            region=self.region,
            config=self.cfg,
        )
        self.assertEqual(result.decision, Level3Decision.SAFE)

    def test_connected_mass_crossing_cut_is_unsafe(self):
        img = np.full((300, 240), 255, dtype=np.uint8)
        cv2.rectangle(img, (90, 80), (150, 220), 0, thickness=3)

        result = analyze_structural_candidate(
            img,
            candidate_y=150,
            region=self.region,
            config=self.cfg,
        )
        self.assertEqual(result.decision, Level3Decision.UNSAFE)
        self.assertIn(
            result.reason,
            {"connected_component_crossing", "strong_diagonal_crossing"},
        )

    def test_strong_diagonal_crossing_is_unsafe(self):
        img = np.full((300, 240), 255, dtype=np.uint8)
        cv2.line(img, (40, 80), (200, 220), 0, thickness=4)

        result = analyze_structural_candidate(
            img,
            candidate_y=150,
            region=self.region,
            config=self.cfg,
        )
        self.assertEqual(result.decision, Level3Decision.UNSAFE)
        self.assertEqual(result.reason, "strong_diagonal_crossing")
        self.assertGreaterEqual(result.metrics["diagonal_crossings"], 1)

    def test_candidate_must_be_covered_by_supplied_image(self):
        img = np.full((100, 240), 255, dtype=np.uint8)
        with self.assertRaises(ValueError):
            analyze_structural_candidate(
                img,
                candidate_y=250,
                region=self.region,
                image_global_start=0,
                config=self.cfg,
            )


if __name__ == "__main__":
    unittest.main()
