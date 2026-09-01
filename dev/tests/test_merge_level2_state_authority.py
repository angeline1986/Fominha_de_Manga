import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from interface_web import processing_web as web


class MergeLevel2StateAuthorityTests(unittest.TestCase):

    def test_row_state_accepts_failure_level2_status_as_validated(self):
        with tempfile.TemporaryDirectory() as td:
            manga = Path(td) / "Manga"
            chapter = manga / "IMG" / "6"
            chapter.mkdir(parents=True)

            failure = {
                "status": "partial",
                "level2_status": "validated",
                "partition": {
                    "level2_validated": False,
                    "resolved_segments": [
                        {
                            "global_start": 0,
                            "global_end": 100,
                        }
                    ],
                    "pending_segments": [
                        {
                            "global_start": 100,
                            "global_end": 200,
                        }
                    ],
                },
            }

            with patch.object(
                web,
                "read_merge_failure",
                return_value=failure,
            ):
                state = web.row_state(
                    manga,
                    chapter,
                )

            self.assertTrue(
                state["merge_level2_validated"],
                "row_state deve reconhecer "
                "failure.level2_status=validated.",
            )

            self.assertTrue(
                state["needs_review"],
                "Level II validado com pending "
                "deve seguir para Review.",
            )

    def test_review_generate_and_row_state_use_same_validation_rule(self):
        failure = {
            "status": "partial",
            "level2_status": "validated",
            "partition": {
                "level2_validated": False,
                "resolved_segments": [
                    {
                        "global_start": 0,
                        "global_end": 100,
                    }
                ],
                "pending_segments": [
                    {
                        "global_start": 100,
                        "global_end": 200,
                    }
                ],
            },
        }

        partition = failure["partition"]

        expected = bool(
            failure.get("level2_status") == "validated"
            or partition.get("level2_validated")
        )

        self.assertTrue(expected)

        # Contrato M8:
        # a interpretação usada por row_state deve
        # ser idêntica à usada pelo fluxo de Review.
        interpreted = web._is_level2_validated(
            failure
        )

        self.assertEqual(
            interpreted,
            expected,
        )


if __name__ == "__main__":
    unittest.main()
