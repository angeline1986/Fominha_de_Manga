import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from processamento.unificacao_imagens import image_stitcher_review as rv


class MergeReviewFinalCompositionSafetyTests(unittest.TestCase):

    def _image(self, path, height, color):
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new(
            "RGB",
            (20, int(height)),
            color,
        ).save(path)

    def _write_json(self, path, payload):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def _build_case(
        self,
        root,
        *,
        left=(0, 3000),
        review_interval=(3000, 9000),
        right=(9000, 12000),
        missing_left_artifact=False,
    ):
        manga = Path(root) / "obra"
        chapter = manga / "IMG" / "6"
        chapter.mkdir(parents=True)

        # Apenas estabelece a altura total real do capítulo.
        self._image(
            chapter / "page-001.png",
            12000,
            (255, 255, 255),
        )

        secondary = manga / "FLUXO_SECUNDARIO"
        level2 = secondary / "MERGE_LEVEL2" / "6"
        review = secondary / "MERGE_REVIEW" / "6"

        left_start, left_end = map(int, left)
        right_start, right_end = map(int, right)
        review_start, review_end = map(
            int,
            review_interval,
        )

        left_height = left_end - left_start
        right_height = right_end - right_start
        review_height = review_end - review_start

        if not missing_left_artifact:
            self._image(
                level2 / "passed-001.png",
                left_height,
                (255, 0, 0),
            )

        self._image(
            level2 / "passed-003.png",
            right_height,
            (255, 255, 0),
        )

        level2_manifest = {
            "schema_version": 1,
            "algorithm": "merge_level2_auto_segments",
            "chapter": "6",
            "total_height": 12000,
            "segments": [
                {
                    "id": 1,
                    "status": "passed",
                    "global_start": left_start,
                    "global_end": left_end,
                    "height": left_height,
                    "artifact": {
                        "file": "passed-001.png",
                        "storage": "MERGE_LEVEL2",
                    },
                },
                {
                    "id": 3,
                    "status": "passed",
                    "global_start": right_start,
                    "global_end": right_end,
                    "height": right_height,
                    "artifact": {
                        "file": "passed-003.png",
                        "storage": "MERGE_LEVEL2",
                    },
                },
            ],
            "artifacts": [
                {
                    "segment_id": 1,
                    "file": "passed-001.png",
                    "global_start": left_start,
                    "global_end": left_end,
                },
                {
                    "segment_id": 3,
                    "file": "passed-003.png",
                    "global_start": right_start,
                    "global_end": right_end,
                },
            ],
            "pending_segments": [
                {
                    "id": 2,
                    "status": "failed",
                    "global_start": review_start,
                    "global_end": review_end,
                    "height": review_height,
                }
            ],
        }

        self._write_json(
            level2 / "merge-level2-manifest.json",
            level2_manifest,
        )

        self._image(
            review / "merged-001.png",
            review_height,
            (0, 255, 0),
        )

        review_manifest = {
            "schema_version": 1,
            "status": "candidate",
            "algorithm": "merge_review_v1",
            "chapter": "6",
            "source_pages": ["page-001.png"],
            "scope": {
                "type": "pending_segments",
                "intervals": [
                    [
                        review_start,
                        review_end,
                    ]
                ],
            },
            "regions": [
                {
                    "region_id": 1,
                    "segment_id": 2,
                    "global_start": review_start,
                    "global_end": review_end,
                    "boundaries": [
                        review_start,
                        review_end,
                    ],
                    "cuts": [],
                    "proposal": [],
                    "source_pages": ["page-001.png"],
                    "outputs": [
                        "merged-001.png",
                    ],
                }
            ],
            "boundaries": [
                review_start,
                review_end,
            ],
            "cuts": [],
            "proposal": [],
            "outputs": [
                "merged-001.png",
            ],
        }

        self._write_json(
            review / "merge-review.json",
            review_manifest,
        )

        return manga

    def _assert_rejected_without_official_merge(
        self,
        manga,
    ):
        ok, msg = rv.approve(
            manga,
            "6",
        )

        self.assertFalse(
            ok,
            msg,
        )

        official = (
            manga
            / "FLUXO_SECUNDARIO"
            / "MERGE"
            / "6"
        )

        self.assertFalse(
            official.exists(),
            (
                "Uma composição estruturalmente inválida "
                "não pode deixar MERGE oficial materializado."
            ),
        )

    def test_approve_rejects_gap_between_level2_and_review(self):
        with tempfile.TemporaryDirectory(
            prefix="fominha_m7_gap_"
        ) as tmp:
            manga = self._build_case(
                tmp,
                left=(0, 3000),
                review_interval=(4000, 9000),
                right=(9000, 12000),
            )

            # Buraco real:
            #
            # Level II  0..3000
            # GAP        3000..4000
            # Review     4000..9000
            # Level II   9000..12000
            self._assert_rejected_without_official_merge(
                manga,
            )

    def test_approve_rejects_overlap_between_level2_and_review(self):
        with tempfile.TemporaryDirectory(
            prefix="fominha_m7_overlap_"
        ) as tmp:
            manga = self._build_case(
                tmp,
                left=(0, 5000),
                review_interval=(4000, 9000),
                right=(9000, 12000),
            )

            # Sobreposição real:
            #
            # Level II  0..5000
            # Review     4000..9000
            #
            # 4000..5000 pertence aos dois.
            self._assert_rejected_without_official_merge(
                manga,
            )

    def test_approve_rejects_missing_level2_artifact(self):
        with tempfile.TemporaryDirectory(
            prefix="fominha_m7_missing_"
        ) as tmp:
            manga = self._build_case(
                tmp,
                left=(0, 3000),
                review_interval=(3000, 9000),
                right=(9000, 12000),
                missing_left_artifact=True,
            )

            # O manifesto declara 0..3000 como PASSED,
            # mas passed-001.png não existe.
            self._assert_rejected_without_official_merge(
                manga,
            )


if __name__ == "__main__":
    unittest.main()
