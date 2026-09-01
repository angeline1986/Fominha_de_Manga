import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from interface_web import processing_web as web


class _Job:
    def __init__(self):
        self.message = ""
        self.progress = 0


class _FakeReview:
    class ReviewSourceLimitError(Exception):
        def as_dict(self):
            return {
                "status": "error",
                "message": str(self),
            }

    def __init__(self):
        self.calls = []

    def generate_candidate(
        self,
        manga,
        chapter,
        max_source_images=None,
        pending_segments=None,
    ):
        self.calls.append(
            {
                "manga": manga,
                "chapter": chapter,
                "max_source_images": max_source_images,
                "pending_segments": pending_segments,
            }
        )

        return (
            True,
            "Review gerado",
            manga / "MERGE_REVIEW" / chapter.name,
        )


class MergeLevel2ReviewGuardTests(unittest.TestCase):

    def test_validated_level2_without_pending_never_generates_whole_chapter_review(self):
        with tempfile.TemporaryDirectory() as td:
            manga = Path(td) / "Manga"
            chapter = manga / "IMG" / "6"
            chapter.mkdir(parents=True)

            failure = {
                "status": "validated",
                "level2_status": "validated",
                "partition": {
                    "status": "validated",
                    "level2_validated": True,
                    "total_height": 200,
                    "resolved_segments": [
                        {
                            "global_start": 0,
                            "global_end": 100,
                        },
                        {
                            "global_start": 100,
                            "global_end": 200,
                        },
                    ],
                    "pending_segments": [],
                },
            }

            fake_review = _FakeReview()
            job = _Job()

            with patch.object(
                web,
                "read_merge_failure",
                return_value=failure,
            ), patch.object(
                web,
                "reviewmod",
                return_value=fake_review,
            ):
                result = web.do_review_generate(
                    job,
                    manga,
                    [chapter],
                    max_source_images=8,
                )

            self.assertEqual(
                fake_review.calls,
                [],
                "Level II validado sem pending não pode "
                "cair em Review de capítulo inteiro.",
            )

            self.assertEqual(
                len(result),
                1,
            )

            self.assertEqual(
                result[0]["status"],
                "error",
            )

            self.assertIn(
                "Level II",
                result[0]["message"],
            )

            self.assertIn(
                "sem segmentos pendentes",
                result[0]["message"],
            )


if __name__ == "__main__":
    unittest.main()
