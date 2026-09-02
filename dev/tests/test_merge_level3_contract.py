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
    search_local_safe_candidate,
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


class Level3LocalSearchTests(unittest.TestCase):
    def setUp(self):
        self.region = Level3PendingRegion(0, 500)
        self.cfg = Level3Config(
            analysis_half_window=80,
            local_search_radius=80,
            local_search_step=2,
            min_component_area=20,
            min_component_height=8,
            hough_threshold=12,
            hough_min_line_length=20,
            hough_max_line_gap=4,
        )

    def test_safe_original_is_not_moved(self):
        img = np.full((400, 240), 255, dtype=np.uint8)
        result = search_local_safe_candidate(
            img,
            candidate_y=200,
            region=self.region,
            config=self.cfg,
        )
        self.assertEqual(result.decision, Level3Decision.SAFE)
        self.assertIsNone(result.alternative_y)
        self.assertFalse(result.metrics["local_search_performed"])

    def test_unsafe_original_can_find_safe_local_alternative(self):
        img = np.full((400, 240), 255, dtype=np.uint8)
        cv2.rectangle(img, (30, 170), (210, 230), 0, thickness=4)

        result = search_local_safe_candidate(
            img,
            candidate_y=200,
            region=self.region,
            config=self.cfg,
        )

        self.assertEqual(result.decision, Level3Decision.SAFE)
        self.assertEqual(result.reason, "local_candidate_safe")
        self.assertIsNotNone(result.alternative_y)
        self.assertLessEqual(abs(result.alternative_y - 200), 80)
        self.assertEqual(
            analyze_structural_candidate(
                img,
                candidate_y=result.alternative_y,
                region=self.region,
                config=self.cfg,
            ).decision,
            Level3Decision.SAFE,
        )

    def test_search_never_escapes_pending_region(self):
        img = np.full((300, 240), 255, dtype=np.uint8)
        region = Level3PendingRegion(100, 230)
        cv2.rectangle(img, (20, 100), (220, 150), 0, thickness=4)

        result = search_local_safe_candidate(
            img,
            candidate_y=120,
            region=region,
            config=Level3Config(
                analysis_half_window=60,
                local_search_radius=100,
                local_search_step=2,
                min_component_area=20,
                min_component_height=8,
                hough_threshold=12,
                hough_min_line_length=20,
                hough_max_line_gap=4,
            ),
        )

        self.assertGreaterEqual(result.metrics["local_search_lower"], 100)
        self.assertLess(result.metrics["local_search_upper"], 230)
        if result.alternative_y is not None:
            self.assertTrue(region.contains(result.alternative_y))

    def test_search_returns_no_forced_cut_when_everything_is_unsafe(self):
        img = np.full((400, 240), 255, dtype=np.uint8)
        # Dense diagonal mesh throughout the entire search area.
        for x in range(-200, 400, 20):
            cv2.line(img, (max(0, x), max(0, -x)),
                     (min(239, x + 399), min(399, 399 - x)),
                     0, thickness=3)

        result = search_local_safe_candidate(
            img,
            candidate_y=200,
            region=self.region,
            config=self.cfg,
        )

        self.assertNotEqual(result.decision, Level3Decision.SAFE)
        self.assertIsNone(result.alternative_y)
        self.assertEqual(result.metrics["safe_alternatives_found"], 0)

    def test_upward_bias_breaks_true_tie(self):
        # The original cut crosses a real structural mass. Outside that mass,
        # the background is uniform and yields symmetric SAFE candidates.
        # Candidates 181 and 219 are equally distant from 200 and have the
        # same structural score; the final tie-break must prefer 181 (up).
        img = np.full((400, 240), 255, dtype=np.uint8)
        cv2.rectangle(img, (60, 188), (180, 212), 0, thickness=3)

        cfg = Level3Config(
            analysis_half_window=20,
            cut_band_half_height=3,
            local_search_radius=40,
            local_search_step=1,
            gaussian_kernel=3,
            min_component_area=20,
            min_component_height=8,
            hough_threshold=12,
            hough_min_line_length=20,
            hough_max_line_gap=4,
            uniform_std_max=8.0,
            safe_edge_density_max=0.001,
        )

        original = analyze_structural_candidate(
            img,
            candidate_y=200,
            region=self.region,
            config=cfg,
        )
        upper = analyze_structural_candidate(
            img,
            candidate_y=181,
            region=self.region,
            config=cfg,
        )
        lower = analyze_structural_candidate(
            img,
            candidate_y=219,
            region=self.region,
            config=cfg,
        )

        self.assertEqual(original.decision, Level3Decision.UNSAFE)
        self.assertEqual(upper.decision, Level3Decision.SAFE)
        self.assertEqual(lower.decision, Level3Decision.SAFE)
        self.assertEqual(
            upper.metrics["edge_density"],
            lower.metrics["edge_density"],
        )
        self.assertEqual(abs(181 - 200), abs(219 - 200))

        result = search_local_safe_candidate(
            img,
            candidate_y=200,
            region=self.region,
            config=cfg,
        )

        self.assertEqual(result.decision, Level3Decision.SAFE)
        self.assertEqual(result.alternative_y, 181)
        self.assertEqual(result.metrics["selected_direction"], "up")

    def test_search_is_deterministic(self):
        img = np.full((400, 240), 255, dtype=np.uint8)
        cv2.rectangle(img, (30, 170), (210, 230), 0, thickness=4)

        first = search_local_safe_candidate(
            img,
            candidate_y=200,
            region=self.region,
            config=self.cfg,
        )
        second = search_local_safe_candidate(
            img,
            candidate_y=200,
            region=self.region,
            config=self.cfg,
        )

        self.assertEqual(first.as_dict(), second.as_dict())


if __name__ == "__main__":
    unittest.main()
