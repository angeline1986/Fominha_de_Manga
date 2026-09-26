import unittest
from unittest.mock import patch

import numpy as np

from processamento.unificacao_imagens.image_stitcher_level3 import (
    Level3Decision,
    Level3Result,
)
from processamento.unificacao_imagens.image_stitcher_level5 import (
    find_global_safe_composition,
)


MODULE = "processamento.unificacao_imagens.image_stitcher_level5"


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


def run_mocked(
    decisions_by_y,
    *,
    end,
    target_height=7000,
    min_chunk_height=3000,
    max_chunk_height=12000,
    scan_step=2,
    progress_callback=None,
):
    image = np.zeros((end, 10), dtype=np.uint8)

    def classify(_image, *, candidate_y, **_kwargs):
        decision, reason = decisions_by_y.get(
            int(candidate_y),
            (Level3Decision.INCONCLUSIVE, "uncertain"),
        )
        return structural_result(decision, int(candidate_y), reason)

    with patch(
        f"{MODULE}.analyze_structural_candidate",
        side_effect=classify,
    ):
        return find_global_safe_composition(
            image,
            global_start=0,
            global_end=end,
            target_height=target_height,
            min_chunk_height=min_chunk_height,
            max_chunk_height=max_chunk_height,
            scan_step=scan_step,
            classifier_workers=1,
            progress_callback=progress_callback,
        )


class TestMergeLevel5Contract(unittest.TestCase):

    def test_rejects_invalid_interval(self):
        image = np.zeros((100, 10), dtype=np.uint8)

        with self.assertRaisesRegex(
            ValueError,
            "Intervalo inválido para Auto-Merge Nível V",
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
        self.assertEqual(got["search_passes"], 0)

    def test_only_safe_candidates_can_form_complete_path(self):
        got = run_mocked(
            {
                6000: (Level3Decision.SAFE, "safe"),
                12000: (Level3Decision.INCONCLUSIVE, "uncertain"),
            },
            end=18000,
            scan_step=1,
        )

        self.assertTrue(got["resolved"])
        self.assertEqual(got["boundaries"], [0, 6000, 18000])
        self.assertEqual(got["chunks"], [6000, 12000])
        self.assertEqual(got["safe_candidates"], 1)
        self.assertEqual(
            got["decision_counts"],
            {
                "INCONCLUSIVE": got["evaluated_candidates"] - 1,
                "SAFE": 1,
            },
        )

    def test_complete_safe_path_reports_boundaries_cuts_and_chunks(self):
        got = run_mocked(
            {
                7000: (Level3Decision.SAFE, "safe"),
                14000: (Level3Decision.SAFE, "safe"),
            },
            end=21000,
            scan_step=1,
        )

        self.assertTrue(got["resolved"])
        self.assertEqual(got["boundaries"], [0, 7000, 14000, 21000])
        self.assertEqual(got["cuts"], [7000, 14000])
        self.assertEqual(got["chunks"], [7000, 7000, 7000])
        self.assertEqual(
            [x["selected_y"] for x in got["selected_diagnostics"]],
            [7000, 14000],
        )

    def test_target_height_selects_best_complete_safe_path(self):
        got = run_mocked(
            {
                6000: (Level3Decision.SAFE, "safe"),
                7000: (Level3Decision.SAFE, "safe"),
                12000: (Level3Decision.SAFE, "safe"),
                14000: (Level3Decision.SAFE, "safe"),
            },
            end=21000,
            scan_step=1,
        )

        self.assertTrue(got["resolved"])
        self.assertEqual(got["boundaries"], [0, 7000, 14000, 21000])
        self.assertEqual(got["chunks"], [7000, 7000, 7000])

    def test_first_parity_can_finish_search_early(self):
        progress = []

        got = run_mocked(
            {
                7000: (Level3Decision.SAFE, "safe"),
                14000: (Level3Decision.SAFE, "safe"),
            },
            end=21000,
            scan_step=2,
            progress_callback=lambda current, total: progress.append(
                (current, total)
            ),
        )

        self.assertTrue(got["resolved"])
        self.assertEqual(got["search_passes"], 1)
        self.assertLess(
            got["evaluated_candidates"],
            got["eligible_candidates"],
        )
        self.assertEqual(
            progress[-1][0],
            got["evaluated_candidates"],
        )
        self.assertEqual(
            progress[-1][1],
            got["eligible_candidates"],
        )

    def test_second_parity_can_complete_path(self):
        got = run_mocked(
            {
                7001: (Level3Decision.SAFE, "safe"),
                14001: (Level3Decision.SAFE, "safe"),
            },
            end=21001,
            scan_step=2,
        )

        self.assertTrue(got["resolved"])
        self.assertEqual(got["search_passes"], 2)
        self.assertEqual(got["boundaries"], [0, 7001, 14001, 21001])
        self.assertEqual(
            got["evaluated_candidates"],
            got["eligible_candidates"],
        )

    def test_without_complete_path_preserves_furthest_safe_prefix(self):
        got = run_mocked(
            {
                7000: (Level3Decision.SAFE, "safe"),
                14000: (Level3Decision.SAFE, "safe"),
            },
            end=28000,
            scan_step=1,
        )

        self.assertFalse(got["resolved"])
        self.assertTrue(got["partial_resolved"])
        self.assertEqual(got["boundaries"], [0, 7000, 14000])
        self.assertEqual(got["cuts"], [7000, 14000])
        self.assertEqual(got["chunks"], [7000, 7000])
        self.assertEqual(got["residual_start"], 14000)
        self.assertEqual(got["residual_end"], 28000)

    def test_without_usable_safe_prefix_returns_unresolved(self):
        got = run_mocked(
            {
                7000: (Level3Decision.INCONCLUSIVE, "uncertain"),
                14000: (Level3Decision.UNSAFE, "unsafe"),
            },
            end=28000,
            scan_step=1,
        )

        self.assertFalse(got["resolved"])
        self.assertFalse(got["partial_resolved"])
        self.assertIsNone(got["boundaries"])
        self.assertEqual(got["cuts"], [])
        self.assertEqual(got["chunks"], [])
        self.assertEqual(got["safe_candidates"], 0)


if __name__ == "__main__":
    unittest.main()
