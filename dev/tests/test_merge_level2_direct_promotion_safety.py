import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from interface_web import processing_web as web
from processamento.unificacao_imagens.image_stitcher import (
    is_chapter_merged,
)


class MergeLevel2DirectPromotionSafetyTests(unittest.TestCase):

    def _png(self, path, color, height):
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new(
            "RGB",
            (20, height),
            color,
        ).save(path, "PNG")

    def _sha256(self, path):
        return hashlib.sha256(
            path.read_bytes()
        ).hexdigest()

    def _chapter(self, root):
        manga = Path(root) / "Manga"
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

        return manga, chapter

    def _segment(
        self,
        idx,
        start,
        end,
        source_file,
        source_global_start,
        source_global_end,
        source_y_start,
        source_y_end,
    ):
        return {
            "id": idx,
            "index": idx,
            "status": "passed",
            "validation": "auto",
            "validated_ok": True,
            "global_start": start,
            "global_end": end,
            "height": end - start,
            "sources": [source_file],
            "source_spans": [
                {
                    "file": source_file,
                    "global_start": source_global_start,
                    "global_end": source_global_end,
                    "source_y_start": source_y_start,
                    "source_y_end": source_y_end,
                }
            ],
        }

    def _write_failure(
        self,
        chapter,
        segments,
        total_height=200,
    ):
        partition = {
            "schema_version": 2,
            "algorithm": (
                "whitespace_v3_level2_partition"
            ),
            "status": "partial",
            "level2_validated": False,
            "total_height": total_height,
            "segments": [
                dict(x)
                for x in segments
            ],
            "resolved_segments": [
                dict(x)
                for x in segments
            ],
            "pending_segments": [],
        }

        failure = {
            "schema_version": 2,
            "chapter": chapter.name,
            "status": "error",
            "message": "fixture M8",
            "partition": partition,
        }

        status_file = web.merge_status_file(
            chapter
        )
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

    def test_direct_promotion_preserves_level2_bytes(self):
        with tempfile.TemporaryDirectory() as td:
            manga, chapter = self._chapter(td)

            segments = [
                self._segment(
                    1,
                    0,
                    100,
                    "page-001.png",
                    0,
                    100,
                    0,
                    100,
                ),
                self._segment(
                    2,
                    100,
                    200,
                    "page-002.png",
                    100,
                    200,
                    0,
                    100,
                ),
            ]

            self._write_failure(
                chapter,
                segments,
            )

            ok, msg, _ = web.validate_merge_level2(
                chapter
            )

            self.assertTrue(ok, msg)
            self.assertTrue(
                is_chapter_merged(chapter)
            )

            level2_dir = (
                manga
                / "FLUXO_SECUNDARIO"
                / "MERGE_LEVEL2"
                / "6"
            )

            merge_dir = (
                manga
                / "FLUXO_SECUNDARIO"
                / "MERGE"
                / "6"
            )

            self.assertEqual(
                self._sha256(
                    level2_dir / "passed-001.png"
                ),
                self._sha256(
                    merge_dir / "merged-001.png"
                ),
            )

            self.assertEqual(
                self._sha256(
                    level2_dir / "passed-002.png"
                ),
                self._sha256(
                    merge_dir / "merged-002.png"
                ),
            )

    def test_direct_promotion_rejects_gap(self):
        with tempfile.TemporaryDirectory() as td:
            manga, chapter = self._chapter(td)

            segments = [
                self._segment(
                    1,
                    0,
                    90,
                    "page-001.png",
                    0,
                    100,
                    0,
                    90,
                ),
                self._segment(
                    2,
                    100,
                    200,
                    "page-002.png",
                    100,
                    200,
                    0,
                    100,
                ),
            ]

            self._write_failure(
                chapter,
                segments,
            )

            ok, msg, _ = web.validate_merge_level2(
                chapter
            )

            # Como a cobertura não é completa,
            # não pode existir promoção oficial.
            self.assertTrue(ok, msg)
            self.assertFalse(
                is_chapter_merged(chapter)
            )

            merge_dir = (
                manga
                / "FLUXO_SECUNDARIO"
                / "MERGE"
                / "6"
            )
            self.assertFalse(
                merge_dir.exists()
            )

    def test_direct_promotion_rejects_overlap(self):
        with tempfile.TemporaryDirectory() as td:
            manga, chapter = self._chapter(td)

            segments = [
                self._segment(
                    1,
                    0,
                    110,
                    "page-001.png",
                    0,
                    100,
                    0,
                    100,
                ),
                self._segment(
                    2,
                    100,
                    200,
                    "page-002.png",
                    100,
                    200,
                    0,
                    100,
                ),
            ]

            self._write_failure(
                chapter,
                segments,
            )

            ok, msg, _ = web.validate_merge_level2(
                chapter
            )

            self.assertTrue(ok, msg)
            self.assertFalse(
                is_chapter_merged(chapter)
            )

            merge_dir = (
                manga
                / "FLUXO_SECUNDARIO"
                / "MERGE"
                / "6"
            )
            self.assertFalse(
                merge_dir.exists()
            )

    def test_direct_promotion_rejects_missing_level2_artifact(self):
        with tempfile.TemporaryDirectory() as td:
            manga, chapter = self._chapter(td)

            segments = [
                self._segment(
                    1,
                    0,
                    100,
                    "page-001.png",
                    0,
                    100,
                    0,
                    100,
                ),
                self._segment(
                    2,
                    100,
                    200,
                    "page-002.png",
                    100,
                    200,
                    0,
                    100,
                ),
            ]

            self._write_failure(
                chapter,
                segments,
            )

            original_promote = (
                web._promote_level2_complete
            )

            def promote_with_missing_artifact(
                ch,
                part,
            ):
                level2_dir = (
                    manga
                    / "FLUXO_SECUNDARIO"
                    / "MERGE_LEVEL2"
                    / "6"
                )

                missing = (
                    level2_dir
                    / "passed-002.png"
                )

                self.assertTrue(
                    missing.is_file(),
                    "Fixture deveria remover um "
                    "artefato já materializado.",
                )

                missing.unlink()

                return original_promote(
                    ch,
                    part,
                )

            from unittest.mock import patch

            with patch.object(
                web,
                "_promote_level2_complete",
                side_effect=(
                    promote_with_missing_artifact
                ),
            ):
                ok, msg, _ = (
                    web.validate_merge_level2(
                        chapter
                    )
                )

            self.assertFalse(ok)
            self.assertIn(
                "ausente",
                msg.lower(),
            )
            self.assertFalse(
                is_chapter_merged(chapter)
            )

            merge_dir = (
                manga
                / "FLUXO_SECUNDARIO"
                / "MERGE"
                / "6"
            )
            self.assertFalse(
                merge_dir.exists()
            )


if __name__ == "__main__":
    unittest.main()
