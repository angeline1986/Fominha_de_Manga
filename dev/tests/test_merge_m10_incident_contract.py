import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from processamento.unificacao_imagens import image_stitcher_review as rv
from processamento.unificacao_imagens import image_stitcher as v3


class MergeM10IncidentContractTests(unittest.TestCase):

    def _review_dir(self, manga, chapter="6"):
        return (
            Path(manga)
            / rv.SECONDARY
            / "01_MERGE_PROCESSAMENTO" / "MERGE_REVIEW"
            / chapter
        )

    def test_approve_rejects_legacy_scoped_review(self):
        """
        Um Review que possui scope, mas não usa o contrato canônico
        pending_segments, jamais pode cair silenciosamente no fluxo
        histórico de promoção.
        """
        with tempfile.TemporaryDirectory() as tmp:
            manga = Path(tmp) / "manga"
            review_dir = self._review_dir(manga)
            review_dir.mkdir(parents=True)

            manifest = {
                "schema_version": 1,
                "algorithm": "merge_review_v1",
                "status": "candidate",
                "scope": {
                    "type": "level2_pending_segments",
                    "segments": [
                        {
                            "global_start": 100,
                            "global_end": 200,
                        }
                    ],
                },
                "boundaries": [100, 200],
                "outputs": ["merged-001.png"],
            }

            (
                review_dir / "merge-review.json"
            ).write_text(
                json.dumps(manifest),
                encoding="utf-8",
            )

            Image.new(
                "RGB",
                (10, 100),
                "white",
            ).save(
                review_dir / "merged-001.png"
            )

            with patch.object(
                rv,
                "_approve_scoped_level2_review",
            ) as scoped:
                ok, msg = rv.approve(manga, "6")

            self.assertFalse(ok)
            self.assertIn(
                "scope não suportado",
                msg,
            )
            scoped.assert_not_called()

            official = (
                manga
                / rv.SECONDARY
                / "02_MERGE"
                / "6"
            )

            self.assertFalse(
                official.exists(),
                "Review legado não pode criar MERGE oficial.",
            )

    def test_approve_routes_canonical_pending_segments_to_scoped(self):
        """
        O contrato atual pending_segments continua encaminhando
        obrigatoriamente para a composição Level II + Review.
        """
        with tempfile.TemporaryDirectory() as tmp:
            manga = Path(tmp) / "manga"
            review_dir = self._review_dir(manga)
            review_dir.mkdir(parents=True)

            manifest = {
                "schema_version": 1,
                "algorithm": "merge_review_v1",
                "status": "candidate",
                "scope": {
                    "type": "pending_segments",
                    "intervals": [[100, 200]],
                },
                "regions": [
                    {
                        "global_start": 100,
                        "global_end": 200,
                        "boundaries": [100, 200],
                        "outputs": ["merged-001.png"],
                    }
                ],
            }

            (
                review_dir / "merge-review.json"
            ).write_text(
                json.dumps(manifest),
                encoding="utf-8",
            )

            with patch.object(
                rv,
                "_approve_scoped_level2_review",
                return_value=(True, "SCOPED_OK"),
            ) as scoped:
                ok, msg = rv.approve(manga, "6")

            self.assertTrue(ok)
            self.assertEqual(msg, "SCOPED_OK")
            scoped.assert_called_once()

    def test_is_chapter_merged_rejects_partial_coverage(self):
        """
        Um manifesto autoconsistente internamente não basta.

        Os outputs oficiais precisam cobrir exatamente toda a altura
        física das páginas-fonte do capítulo.
        """
        with tempfile.TemporaryDirectory() as tmp:
            chapter = Path(tmp) / "IMG" / "6"
            chapter.mkdir(parents=True)

            for index in range(1, 4):
                Image.new(
                    "RGB",
                    (10, 100),
                    "white",
                ).save(
                    chapter / f"page-{index:03d}.png"
                )

            merge_dir = v3.merge_output_dir(chapter)
            merge_dir.mkdir(parents=True)

            Image.new(
                "RGB",
                (10, 100),
                "white",
            ).save(
                merge_dir / "merged-001.png"
            )

            manifest = {
                "schema_version": 1,
                "algorithm": "merge_review_v1_approved",
                "status": "approved",
                "source_total_height": 100,
                "merged_images": 1,
                "outputs": [
                    {
                        "file": "merged-001.png",
                        "width": 10,
                        "height": 100,
                        "global_start": 100,
                        "global_end": 200,
                    }
                ],
                "validation": {
                    "ok": True,
                    "coverage_start": 0,
                    "coverage_end": 100,
                },
            }

            v3.merge_manifest_path(chapter).write_text(
                json.dumps(manifest),
                encoding="utf-8",
            )

            self.assertFalse(
                v3.is_chapter_merged(chapter),
                "MERGE parcial jamais pode ser reconhecido "
                "como capítulo concluído.",
            )


if __name__ == "__main__":
    unittest.main()
