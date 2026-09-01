import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from interface_web import processing_web as web
from processamento.unificacao_imagens.image_stitcher import (
    is_chapter_merged,
)


class MergeLevel2StateMachineTests(unittest.TestCase):

    def _png(self, path, color, height):
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new(
            "RGB",
            (20, height),
            color,
        ).save(path, "PNG")

    def test_level2_all_passed_finishes_without_review(self):
        with tempfile.TemporaryDirectory() as td:
            manga = Path(td) / "Manga"
            chapter = manga / "IMG" / "6"
            chapter.mkdir(parents=True)

            self._png(
                chapter / "page-001.png",
                "red",
                100,
            )
            self._png(
                chapter / "page-002.png",
                "blue",
                100,
            )

            # Estado produzido pelo Level I:
            # dois segmentos aproveitáveis e nenhum FAILED.
            partition = {
                "schema_version": 2,
                "algorithm": "whitespace_v3_level2_partition",
                "status": "partial",
                "level2_validated": False,
                "total_height": 200,
                "segments": [
                    {
                        "id": 1,
                        "index": 1,
                        "status": "passed",
                        "validation": "auto",
                        "validated_ok": True,
                        "global_start": 0,
                        "global_end": 100,
                        "height": 100,
                        "sources": ["page-001.png"],
                        "source_spans": [
                            {
                                "file": "page-001.png",
                                "global_start": 0,
                                "global_end": 100,
                                "source_y_start": 0,
                                "source_y_end": 100,
                            }
                        ],
                    },
                    {
                        "id": 2,
                        "index": 2,
                        "status": "passed",
                        "validation": "auto",
                        "validated_ok": True,
                        "global_start": 100,
                        "global_end": 200,
                        "height": 100,
                        "sources": ["page-002.png"],
                        "source_spans": [
                            {
                                "file": "page-002.png",
                                "global_start": 100,
                                "global_end": 200,
                                "source_y_start": 0,
                                "source_y_end": 100,
                            }
                        ],
                    },
                ],
                "resolved_segments": [],
                "pending_segments": [],
            }

            # resolved_segments precisa refletir os PASSED
            # recebidos do particionamento.
            partition["resolved_segments"] = [
                dict(x)
                for x in partition["segments"]
            ]

            failure = {
                "schema_version": 2,
                "chapter": "6",
                "status": "error",
                "message": "Level I não concluiu.",
                "partition": partition,
            }

            status_file = web.merge_status_file(chapter)
            status_file.parent.mkdir(
                parents=True,
                exist_ok=True,
            )
            status_file.write_text(
                json.dumps(
                    failure,
                    ensure_ascii=False,
                    indent=2,
                ) + "\n",
                encoding="utf-8",
            )

            ok, msg, part = web.validate_merge_level2(
                chapter
            )

            self.assertTrue(ok, msg)
            self.assertTrue(
                part["level2_validated"]
            )
            self.assertEqual(
                part["pending_segments"],
                [],
            )

            # Contrato M8:
            # se não sobrou FAILED, o fluxo terminou.
            self.assertTrue(
                is_chapter_merged(chapter),
                "Level II 100% PASSED deveria "
                "materializar o MERGE oficial.",
            )

            review_dir = (
                manga
                / "FLUXO_SECUNDARIO"
                / "MERGE_REVIEW"
                / "6"
            )

            self.assertFalse(
                review_dir.exists(),
                "Level II 100% PASSED não deveria "
                "criar ou depender de MERGE_REVIEW.",
            )

            state = web.row_state(
                manga,
                chapter,
            )

            self.assertEqual(
                state["merge_state"],
                "concluido",
            )
            self.assertFalse(
                state["needs_review"],
            )


if __name__ == "__main__":
    unittest.main()
