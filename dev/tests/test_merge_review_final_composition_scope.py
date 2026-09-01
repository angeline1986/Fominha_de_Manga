import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from processamento.unificacao_imagens import image_stitcher_review as rv


class MergeReviewFinalCompositionScopeTests(unittest.TestCase):

    def _png(self, path, height, color):
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new(
            "RGB",
            (12, int(height)),
            color,
        ).save(path)

    def _prepare_level2(
        self,
        manga,
        *,
        total_height,
        passed,
        pending,
    ):
        level2 = (
            manga
            / "FLUXO_SECUNDARIO"
            / "MERGE_LEVEL2"
            / "6"
        )
        level2.mkdir(parents=True, exist_ok=True)

        segments = []
        artifacts = []

        for item in passed:
            segment_id = item["id"]
            start = item["start"]
            end = item["end"]
            filename = item["file"]

            self._png(
                level2 / filename,
                end - start,
                item["color"],
            )

            segments.append(
                {
                    "id": segment_id,
                    "index": segment_id,
                    "status": "passed",
                    "validation": "auto",
                    "global_start": start,
                    "global_end": end,
                    "height": end - start,
                    "artifact": {
                        "file": filename,
                        "storage": "MERGE_LEVEL2",
                    },
                }
            )

            artifacts.append(
                {
                    "segment_id": segment_id,
                    "file": filename,
                    "global_start": start,
                    "global_end": end,
                    "validation": "auto",
                    "validated_ok": True,
                }
            )

        pending_segments = []

        for item in pending:
            pending_segments.append(
                {
                    "id": item["id"],
                    "index": item["id"],
                    "status": "failed",
                    "validation": "review_required",
                    "global_start": item["start"],
                    "global_end": item["end"],
                    "height": item["end"] - item["start"],
                }
            )

        payload = {
            "schema_version": 1,
            "algorithm": "merge_level2_auto_segments",
            "chapter": "6",
            "total_height": total_height,
            "segments": segments,
            "artifacts": artifacts,
            "pending_segments": pending_segments,
        }

        (
            level2
            / "merge-level2-manifest.json"
        ).write_text(
            json.dumps(payload, indent=2),
            encoding="utf-8",
        )

        return level2

    def _prepare_review(
        self,
        manga,
        *,
        scope_intervals,
        regions,
    ):
        review = (
            manga
            / "FLUXO_SECUNDARIO"
            / "MERGE_REVIEW"
            / "6"
        )
        review.mkdir(parents=True, exist_ok=True)

        all_outputs = []

        for region in regions:
            for output in region["outputs_spec"]:
                self._png(
                    review / output["file"],
                    output["end"] - output["start"],
                    output["color"],
                )
                all_outputs.append(output["file"])

        manifest_regions = []

        for region in regions:
            manifest_regions.append(
                {
                    "segment_id": region["segment_id"],
                    "global_start": region["start"],
                    "global_end": region["end"],
                    "boundaries": region["boundaries"],
                    "outputs": [
                        item["file"]
                        for item in region["outputs_spec"]
                    ],
                }
            )

        payload = {
            "schema_version": 1,
            "algorithm": "merge_review_v1",
            "chapter": "6",
            "status": "candidate",
            "scope": {
                "type": "pending_segments",
                "intervals": scope_intervals,
            },
            "regions": manifest_regions,
            "outputs": all_outputs,
            "boundaries": (
                manifest_regions[0]["boundaries"]
                if len(manifest_regions) == 1
                else []
            ),
        }

        (
            review
            / "merge-review.json"
        ).write_text(
            json.dumps(payload, indent=2),
            encoding="utf-8",
        )

        return review

    def test_approve_composes_multiple_pending_regions(self):
        with tempfile.TemporaryDirectory() as temp:
            manga = Path(temp) / "Manga"

            self._prepare_level2(
                manga,
                total_height=12000,
                passed=[
                    {
                        "id": 1,
                        "start": 0,
                        "end": 2000,
                        "file": "passed-001.png",
                        "color": "red",
                    },
                    {
                        "id": 3,
                        "start": 4000,
                        "end": 8000,
                        "file": "passed-003.png",
                        "color": "yellow",
                    },
                    {
                        "id": 5,
                        "start": 10000,
                        "end": 12000,
                        "file": "passed-005.png",
                        "color": "purple",
                    },
                ],
                pending=[
                    {
                        "id": 2,
                        "start": 2000,
                        "end": 4000,
                    },
                    {
                        "id": 4,
                        "start": 8000,
                        "end": 10000,
                    },
                ],
            )

            self._prepare_review(
                manga,
                scope_intervals=[
                    [2000, 4000],
                    [8000, 10000],
                ],
                regions=[
                    {
                        "segment_id": 2,
                        "start": 2000,
                        "end": 4000,
                        "boundaries": [
                            2000,
                            4000,
                        ],
                        "outputs_spec": [
                            {
                                "file": "merged-001.png",
                                "start": 2000,
                                "end": 4000,
                                "color": "green",
                            },
                        ],
                    },
                    {
                        "segment_id": 4,
                        "start": 8000,
                        "end": 10000,
                        "boundaries": [
                            8000,
                            10000,
                        ],
                        "outputs_spec": [
                            {
                                "file": "merged-002.png",
                                "start": 8000,
                                "end": 10000,
                                "color": "blue",
                            },
                        ],
                    },
                ],
            )

            ok, message = rv.approve(
                manga,
                "6",
            )

            self.assertTrue(
                ok,
                message,
            )

            official = (
                manga
                / "FLUXO_SECUNDARIO"
                / "MERGE"
                / "6"
            )

            payload = json.loads(
                (
                    official
                    / "merge-manifest.json"
                ).read_text(
                    encoding="utf-8"
                )
            )

            outputs = payload["outputs"]

            self.assertEqual(
                len(outputs),
                5,
            )

            self.assertEqual(
                [
                    (
                        item["global_start"],
                        item["global_end"],
                        item["source_stage"],
                    )
                    for item in outputs
                ],
                [
                    (0, 2000, "level2"),
                    (2000, 4000, "review"),
                    (4000, 8000, "level2"),
                    (8000, 10000, "review"),
                    (10000, 12000, "level2"),
                ],
            )

    def test_approve_rejects_stale_review_scope(self):
        with tempfile.TemporaryDirectory() as temp:
            manga = Path(temp) / "Manga"

            self._prepare_level2(
                manga,
                total_height=8000,
                passed=[
                    {
                        "id": 1,
                        "start": 0,
                        "end": 2000,
                        "file": "passed-001.png",
                        "color": "red",
                    },
                    {
                        "id": 3,
                        "start": 4000,
                        "end": 8000,
                        "file": "passed-003.png",
                        "color": "yellow",
                    },
                ],
                pending=[
                    {
                        "id": 2,
                        "start": 2000,
                        "end": 4000,
                    },
                ],
            )

            # O conteúdo materializado ainda cobre 2000..4000,
            # mas o scope declara 2000..4500.
            #
            # Sem comparar o scope do Review com o pending
            # atual do Level II, um Review stale poderia ser
            # promovido silenciosamente.
            self._prepare_review(
                manga,
                scope_intervals=[
                    [2000, 4500],
                ],
                regions=[
                    {
                        "segment_id": 2,
                        "start": 2000,
                        "end": 4000,
                        "boundaries": [
                            2000,
                            4000,
                        ],
                        "outputs_spec": [
                            {
                                "file": "merged-001.png",
                                "start": 2000,
                                "end": 4000,
                                "color": "green",
                            },
                        ],
                    },
                ],
            )

            ok, message = rv.approve(
                manga,
                "6",
            )

            self.assertFalse(
                ok,
                (
                    "Review stale foi promovido "
                    f"indevidamente: {message}"
                ),
            )

            self.assertFalse(
                (
                    manga
                    / "FLUXO_SECUNDARIO"
                    / "MERGE"
                    / "6"
                ).exists(),
                "MERGE oficial não deveria ser criado.",
            )


if __name__ == "__main__":
    unittest.main()
