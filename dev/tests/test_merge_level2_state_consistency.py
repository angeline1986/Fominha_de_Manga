import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from interface_web import processing_web as web


class MergeLevel2StateConsistencyTests(unittest.TestCase):

    def test_validated_without_pending_and_without_official_merge_is_not_review(self):
        failure = {
            "status": "validated",
            "level2_status": "validated",
            "partition": {
                "total_height": 200,
                "resolved_segments": [
                    {
                        "id": 1,
                        "global_start": 0,
                        "global_end": 100,
                        "status": "passed",
                    },
                    {
                        "id": 2,
                        "global_start": 100,
                        "global_end": 200,
                        "status": "passed",
                    },
                ],
                "pending_segments": [],
                "level2_validated": True,
                "status": "validated",
            },
        }

        with tempfile.TemporaryDirectory() as td:
            manga = Path(td) / "Manga"
            chapter = manga / "IMG" / "6"
            chapter.mkdir(parents=True)

            with patch.object(
                web,
                "read_merge_failure",
                return_value=failure,
            ):
                state = web.row_state(manga, chapter)

        self.assertTrue(state["merge_failed"])
        self.assertTrue(state["merge_level2_validated"])

        self.assertFalse(
            state["needs_review"],
            "Level II validado sem pending não pode ser enviado ao Review.",
        )

        self.assertNotEqual(
            state["merge_state"],
            "pendente_review",
            "Estado inconsistente não pode ser apresentado como Review pendente.",
        )

        self.assertNotEqual(
            state["merge_state"],
            "novo",
            "Estado persistido de Level II validado também não pode regredir para novo.",
        )


if __name__ == "__main__":
    unittest.main()
