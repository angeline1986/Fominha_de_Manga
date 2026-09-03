import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from processamento.unificacao_imagens import image_stitcher_review as rv


class MergeReviewFinalCompositionTests(unittest.TestCase):

    def _save(self, path, color, height=3000):
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (20, height), color).save(path)

    def test_approve_composes_level2_passed_and_review_in_global_order(self):
        with tempfile.TemporaryDirectory(
            prefix="fominha_m7_compose_"
        ) as tmp:
            manga = Path(tmp) / "obra"
            chapter = manga / "IMG" / "6"
            chapter.mkdir(parents=True)

            # Fonte original: altura total oficial do capítulo.
            Image.new(
                "RGB",
                (20, 12000),
                (255, 255, 255),
            ).save(chapter / "page-001.png")

            secondary = manga / "FLUXO_SECUNDARIO"

            level2 = secondary / "01_MERGE_PROCESSAMENTO" / "MERGE_LEVEL2" / "6"
            review = secondary / "01_MERGE_PROCESSAMENTO" / "MERGE_REVIEW" / "6"

            # Level II preserva as regiões PASSED.
            self._save(
                level2 / "passed-001.png",
                (255, 0, 0),
            )
            self._save(
                level2 / "passed-003.png",
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
                        "global_start": 0,
                        "global_end": 3000,
                        "height": 3000,
                        "artifact": {
                            "file": "passed-001.png",
                            "storage": "MERGE_LEVEL2",
                        },
                    },
                    {
                        "id": 3,
                        "status": "passed",
                        "global_start": 9000,
                        "global_end": 12000,
                        "height": 3000,
                        "artifact": {
                            "file": "passed-003.png",
                            "storage": "MERGE_LEVEL2",
                        },
                    },
                ],
                "artifacts": [
                    {
                        "file": "passed-001.png",
                        "global_start": 0,
                        "global_end": 3000,
                    },
                    {
                        "file": "passed-003.png",
                        "global_start": 9000,
                        "global_end": 12000,
                    },
                ],
                "pending_segments": [
                    {
                        "id": 2,
                        "status": "failed",
                        "global_start": 3000,
                        "global_end": 9000,
                        "height": 6000,
                    },
                ],
            }

            level2.mkdir(parents=True, exist_ok=True)
            (
                level2 / "merge-level2-manifest.json"
            ).write_text(
                json.dumps(level2_manifest, indent=2) + "\n",
                encoding="utf-8",
            )

            # Review resolve exatamente a região FAILED.
            self._save(
                review / "merged-001.png",
                (0, 255, 0),
            )
            self._save(
                review / "merged-002.png",
                (0, 0, 255),
            )

            review_manifest = {
                "schema_version": 1,
                "algorithm": "merge_review_v1",
                "source_pages": ["page-001.png"],
                "scope": {
                    "type": "pending_segments",
                    "intervals": [[3000, 9000]],
                },
                "regions": [
                    {
                        "global_start": 3000,
                        "global_end": 9000,
                        "boundaries": [
                            3000,
                            6000,
                            9000,
                        ],
                        "outputs": [
                            "merged-001.png",
                            "merged-002.png",
                        ],
                    }
                ],
                "boundaries": [
                    3000,
                    6000,
                    9000,
                ],
                "cuts": [],
                "proposal": [],
                "outputs": [
                    "merged-001.png",
                    "merged-002.png",
                ],
            }

            review.mkdir(parents=True, exist_ok=True)
            (
                review / "merge-review.json"
            ).write_text(
                json.dumps(review_manifest, indent=2) + "\n",
                encoding="utf-8",
            )

            ok, msg = rv.approve(manga, "6")

            self.assertTrue(ok, msg)

            official = secondary / "02_MERGE" / "6"
            outputs = sorted(
                official.glob("merged-*.png")
            )

            self.assertEqual(len(outputs), 4)

            # M7 não pode re-renderizar nenhum artefato já
            # materializado pelo Level II ou pelo Review.
            #
            # A composição final apenas renomeia/copia os arquivos;
            # portanto os bytes precisam permanecer idênticos.
            source_files = [
                level2 / "passed-001.png",
                review / "merged-001.png",
                review / "merged-002.png",
                level2 / "passed-003.png",
            ]

            for source_file, official_file in zip(
                source_files,
                outputs,
            ):
                self.assertEqual(
                    source_file.read_bytes(),
                    official_file.read_bytes(),
                    (
                        "Artefato final foi re-renderizado ou "
                        "alterado durante a composição: "
                        f"{source_file.name}"
                    ),
                )

            expected = [
                ((255, 0, 0), 3000),
                ((0, 255, 0), 3000),
                ((0, 0, 255), 3000),
                ((255, 255, 0), 3000),
            ]

            for path, (color, height) in zip(
                outputs,
                expected,
            ):
                with Image.open(path) as im:
                    actual = im.convert("RGB")
                    self.assertEqual(
                        actual.size,
                        (20, height),
                    )
                    self.assertEqual(
                        actual.getpixel((10, height // 2)),
                        color,
                    )

            manifest = json.loads(
                (
                    official / "merge-manifest.json"
                ).read_text(encoding="utf-8")
            )

            self.assertEqual(
                [
                    [
                        int(item["global_start"]),
                        int(item["global_end"]),
                    ]
                    for item in manifest["outputs"]
                ],
                [
                    [0, 3000],
                    [3000, 6000],
                    [6000, 9000],
                    [9000, 12000],
                ],
            )

            self.assertEqual(
                manifest["validation"]["coverage_start"],
                0,
            )
            self.assertEqual(
                manifest["validation"]["coverage_end"],
                12000,
            )


if __name__ == "__main__":
    unittest.main()
