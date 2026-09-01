import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageChops

from interface_web import processing_web as pw


class MergeLevel2Tests(unittest.TestCase):
    def test_materialization_preserves_mid_page_spans_exactly(self):
        with tempfile.TemporaryDirectory(prefix="fominha_m4_midpage_") as tmp:
            manga = Path(tmp) / "obra"
            ch = manga / "IMG" / "6"
            ch.mkdir(parents=True)

            # Fonte 1:
            # y=0..49   vermelho
            # y=50..99  verde
            p1 = ch / "page-001.png"
            im1 = Image.new("RGB", (20, 100), "red")
            green = Image.new("RGB", (20, 50), (0, 255, 0))
            im1.paste(green, (0, 50))
            im1.save(p1)

            # Fonte 2:
            # y=0..49   azul
            # y=50..99  amarelo
            p2 = ch / "page-002.png"
            im2 = Image.new("RGB", (20, 100), "blue")
            yellow = Image.new("RGB", (20, 50), (255, 255, 0))
            im2.paste(yellow, (0, 50))
            im2.save(p2)

            # Segmento global 50..150:
            # - últimos 50 px da page-001
            # - primeiros 50 px da page-002
            segment = {
                "id": 1,
                "index": 1,
                "status": "passed",
                "validation": "auto",
                "global_start": 50,
                "global_end": 150,
                "height": 100,
                "sources": ["page-001.png", "page-002.png"],
                "source_spans": [
                    {
                        "file": "page-001.png",
                        "global_start": 0,
                        "global_end": 100,
                        "source_y_start": 50,
                        "source_y_end": 100,
                    },
                    {
                        "file": "page-002.png",
                        "global_start": 100,
                        "global_end": 200,
                        "source_y_start": 0,
                        "source_y_end": 50,
                    },
                ],
            }

            partition = {
                "schema_version": 2,
                "algorithm": "m4_midpage_regression",
                "status": "partial",
                "level2_validated": False,
                "total_height": 200,
                "segments": [dict(segment)],
                "resolved_segments": [dict(segment)],
                "pending_segments": [],
            }

            failure = {
                "schema_version": 1,
                "chapter": "6",
                "status": "error",
                "message": "regression fixture",
                "partition": partition,
            }

            with patch.object(pw, "read_merge_failure", return_value=failure):
                ok, msg, result = pw.validate_merge_level2(ch)

            self.assertTrue(ok, msg)
            self.assertIsNotNone(result)

            out = (
                manga
                / "FLUXO_SECUNDARIO"
                / "MERGE_LEVEL2"
                / "6"
                / "passed-001.png"
            )
            self.assertTrue(out.is_file())

            expected = Image.new("RGB", (20, 100))
            expected.paste(
                Image.new("RGB", (20, 50), (0, 255, 0)),
                (0, 0),
            )
            expected.paste(
                Image.new("RGB", (20, 50), (0, 0, 255)),
                (0, 50),
            )

            with Image.open(out) as generated:
                actual = generated.convert("RGB")
                self.assertEqual(actual.size, (20, 100))

                diff = ImageChops.difference(actual, expected)
                self.assertIsNone(
                    diff.getbbox(),
                    "O Level II deslocou, perdeu ou duplicou pixels.",
                )


    def test_validation_preserves_pending_between_passed_segments(self):
        with tempfile.TemporaryDirectory(prefix="fominha_m4_partition_") as tmp:
            manga = Path(tmp) / "obra"
            ch = manga / "IMG" / "6"
            ch.mkdir(parents=True)

            Image.new("RGB", (20, 100), (255, 0, 0)).save(
                ch / "page-001.png"
            )
            Image.new("RGB", (20, 100), (0, 255, 0)).save(
                ch / "page-002.png"
            )
            Image.new("RGB", (20, 100), (0, 0, 255)).save(
                ch / "page-003.png"
            )

            passed_1 = {
                "id": 1,
                "index": 1,
                "status": "passed",
                "validation": "auto",
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
            }

            failed = {
                "id": 2,
                "index": 2,
                "status": "failed",
                "validation": "review_required",
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
            }

            passed_3 = {
                "id": 3,
                "index": 3,
                "status": "passed",
                "validation": "auto",
                "global_start": 200,
                "global_end": 300,
                "height": 100,
                "sources": ["page-003.png"],
                "source_spans": [
                    {
                        "file": "page-003.png",
                        "global_start": 200,
                        "global_end": 300,
                        "source_y_start": 0,
                        "source_y_end": 100,
                    }
                ],
            }

            partition = {
                "schema_version": 2,
                "algorithm": "m4_partition_regression",
                "status": "partial",
                "level2_validated": False,
                "total_height": 300,
                "segments": [
                    dict(passed_1),
                    dict(failed),
                    dict(passed_3),
                ],
                "resolved_segments": [
                    dict(passed_1),
                    dict(passed_3),
                ],
                "pending_segments": [
                    dict(failed),
                ],
            }

            failure = {
                "schema_version": 1,
                "chapter": "6",
                "status": "error",
                "message": "regression fixture",
                "partition": partition,
            }

            with patch.object(
                pw,
                "read_merge_failure",
                return_value=failure,
            ):
                ok, msg, result = pw.validate_merge_level2(ch)

            self.assertTrue(ok, msg)
            self.assertIsNotNone(result)

            self.assertEqual(
                [
                    (
                        int(x["global_start"]),
                        int(x["global_end"]),
                        x["status"],
                    )
                    for x in result["segments"]
                ],
                [
                    (0, 100, "passed"),
                    (100, 200, "failed"),
                    (200, 300, "passed"),
                ],
            )

            self.assertEqual(
                [
                    (
                        int(x["global_start"]),
                        int(x["global_end"]),
                    )
                    for x in result["pending_segments"]
                ],
                [(100, 200)],
            )

            dest = (
                manga
                / "FLUXO_SECUNDARIO"
                / "MERGE_LEVEL2"
                / "6"
            )

            self.assertTrue((dest / "passed-001.png").is_file())
            self.assertFalse((dest / "passed-002.png").exists())
            self.assertTrue((dest / "passed-003.png").is_file())

            manifest = __import__("json").loads(
                (dest / "merge-level2-manifest.json").read_text(
                    encoding="utf-8"
                )
            )

            self.assertEqual(
                [
                    int(x["segment_id"])
                    for x in manifest["artifacts"]
                ],
                [1, 3],
            )

            self.assertEqual(
                manifest["coverage"]["auto_segments"],
                [[0, 100], [200, 300]],
            )

            self.assertEqual(
                [
                    [
                        int(x["global_start"]),
                        int(x["global_end"]),
                    ]
                    for x in manifest["pending_segments"]
                ],
                [[100, 200]],
            )

            with Image.open(dest / "passed-001.png") as im:
                self.assertEqual(
                    im.convert("RGB").getpixel((10, 50)),
                    (255, 0, 0),
                )

            with Image.open(dest / "passed-003.png") as im:
                self.assertEqual(
                    im.convert("RGB").getpixel((10, 50)),
                    (0, 0, 255),
                )


if __name__ == "__main__":
    unittest.main()
