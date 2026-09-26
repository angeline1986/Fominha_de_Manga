import unittest
from unittest.mock import patch

import numpy as np

from processamento.unificacao_imagens.image_stitcher_level3 import (
    Level3Decision,
    Level3Result,
)
from processamento.unificacao_imagens.image_stitcher_level4 import (
    estimate_directed_validation_count,
    find_global_safe_composition,
)


MODULE = "processamento.unificacao_imagens.image_stitcher_level4"


def structural_result(decision, y, reason="safe"):
    return Level3Result(
        decision=decision,
        candidate_y=y,
        reason=reason,
        region_start=0,
        region_end=24000,
        metrics={"edge_density": 0.01},
        alternative_y=None,
    )


def preselection(candidates):
    return {
        "coarse_positions": len(candidates),
        "bins": 1,
        "seed_count": len(candidates),
        "shortlisted_candidates": len(candidates),
        "seed_metrics": [],
    }


def run_mocked(candidates, decisions, *, end, progress_callback=None):
    results = [
        structural_result(decision, y, reason)
        for y, (decision, reason) in zip(candidates, decisions)
    ]
    image = np.zeros((end, 10), dtype=np.uint8)

    with (
        patch(
            f"{MODULE}._shortlist",
            return_value=(candidates, preselection(candidates)),
        ),
        patch(
            f"{MODULE}.analyze_structural_candidate",
            side_effect=results,
        ),
    ):
        return find_global_safe_composition(
            image,
            global_start=0,
            global_end=end,
            progress_callback=progress_callback,
        )


class TestMergeLevel4Contract(unittest.TestCase):

    def test_rejects_invalid_interval(self):
        image = np.zeros((100, 10), dtype=np.uint8)

        with self.assertRaisesRegex(
            ValueError,
            "Intervalo inválido para Auto-Merge Nível IV",
        ):
            find_global_safe_composition(
                image,
                global_start=100,
                global_end=100,
            )

    def test_interval_within_max_height_skips_validation(self):
        image = np.zeros((10000, 10), dtype=np.uint8)

        with patch(f"{MODULE}.analyze_structural_candidate") as analyze:
            got = find_global_safe_composition(
                image,
                global_start=0,
                global_end=10000,
            )

        analyze.assert_not_called()
        self.assertTrue(got["resolved"])
        self.assertEqual(got["boundaries"], [0, 10000])
        self.assertEqual(got["cuts"], [])
        self.assertEqual(got["chunks"], [10000])
        self.assertEqual(got["evaluated_candidates"], 0)
        self.assertEqual(got["safe_candidates"], 0)
        self.assertEqual(got["strategy"], "directed_coarse_refine_v1")

    def test_only_safe_candidates_can_form_complete_path(self):
        got = run_mocked(
            [6000, 12000],
            [
                (Level3Decision.SAFE, "safe"),
                (Level3Decision.INCONCLUSIVE, "uncertain"),
            ],
            end=18000,
        )

        self.assertTrue(got["resolved"])
        self.assertEqual(got["boundaries"], [0, 6000, 18000])
        self.assertEqual(got["chunks"], [6000, 12000])
        self.assertEqual(got["safe_candidates"], 1)
        self.assertEqual(
            got["decision_counts"],
            {"SAFE": 1, "INCONCLUSIVE": 1},
        )

    def test_without_complete_safe_path_returns_unresolved(self):
        got = run_mocked(
            [6000, 12000],
            [
                (Level3Decision.INCONCLUSIVE, "uncertain"),
                (Level3Decision.INCONCLUSIVE, "uncertain"),
            ],
            end=18000,
        )

        self.assertFalse(got["resolved"])
        self.assertIsNone(got["boundaries"])
        self.assertEqual(got["cuts"], [])
        self.assertEqual(got["chunks"], [])
        self.assertEqual(got["safe_candidates"], 0)

    def test_target_height_selects_best_complete_safe_path(self):
        got = run_mocked(
            [6000, 7000, 12000, 14000],
            [(Level3Decision.SAFE, "safe")] * 4,
            end=21000,
        )

        self.assertTrue(got["resolved"])
        self.assertEqual(
            got["boundaries"],
            [0, 7000, 14000, 21000],
        )
        self.assertEqual(got["chunks"], [7000, 7000, 7000])
        self.assertEqual(got["cuts"], [7000, 14000])
        self.assertEqual(
            [x["selected_y"] for x in got["selected_diagnostics"]],
            [7000, 14000],
        )

    def test_progress_reports_every_shortlisted_candidate(self):
        progress = []

        run_mocked(
            [6000, 12000],
            [(Level3Decision.SAFE, "safe")] * 2,
            end=18000,
            progress_callback=lambda current, total: progress.append(
                (current, total)
            ),
        )

        self.assertEqual(progress, [(1, 2), (2, 2)])

    def test_estimate_is_zero_without_eligible_cut_region(self):
        self.assertEqual(
            estimate_directed_validation_count(
                0,
                5000,
                min_chunk_height=3000,
            ),
            0,
        )

    def test_estimate_is_positive_for_large_residual(self):
        self.assertGreater(
            estimate_directed_validation_count(
                0,
                24000,
                min_chunk_height=3000,
                bin_height=3000,
                seeds_per_bin=3,
                refine_radius=128,
                refine_step=8,
            ),
            0,
        )


if __name__ == "__main__":
    unittest.main()
