#!/usr/bin/env python3
import unittest

from processamento.unificacao_imagens.image_stitcher_level3 import (
    Level3Decision,
    Level3PendingRegion,
    Level3Result,
    normalize_pending_segments,
    placeholder_structural_evaluation,
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
        self.assertEqual(
            result.as_dict(),
            {
                "decision": "UNSAFE",
                "candidate_y": 250,
                "reason": "example_reason",
                "region": {
                    "global_start": 100,
                    "global_end": 500,
                },
                "metrics": {"edge_density": 0.12},
                "alternative_y": 220,
            },
        )


if __name__ == "__main__":
    unittest.main()
