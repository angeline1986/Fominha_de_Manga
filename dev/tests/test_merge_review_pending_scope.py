import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from processamento.unificacao_imagens import image_stitcher as v3
from processamento.unificacao_imagens import image_stitcher_review as rv


class MergeReviewPendingScopeTests(unittest.TestCase):
    def test_review_candidate_is_restricted_to_pending_interval(self):
        with tempfile.TemporaryDirectory(prefix="fominha_m5_scope_") as tmp:
            manga = Path(tmp) / "obra"
            chapter = manga / "IMG" / "6"
            chapter.mkdir(parents=True)

            # Duas fontes de 6000px:
            #
            # page-001 = 0..6000
            # page-002 = 6000..12000
            #
            # O FAILED é 3000..9000:
            # - começa no meio de page-001;
            # - termina no meio de page-002.
            #
            # Cada fonte possui duas metades de cores diferentes.
            # O Review deve preservar exatamente:
            #
            # page-001 y=3000..6000 -> verde
            # page-002 y=0..3000    -> azul
            #
            # Vermelho e amarelo estão fora do FAILED e não podem
            # aparecer no output.

            page1 = Image.new(
                "RGB", (20, 6000), (255, 0, 0)
            )
            page1.paste(
                Image.new("RGB", (20, 3000), (0, 255, 0)),
                (0, 3000),
            )
            page1.save(chapter / "page-001.png")

            page2 = Image.new(
                "RGB", (20, 6000), (0, 0, 255)
            )
            page2.paste(
                Image.new("RGB", (20, 3000), (255, 255, 0)),
                (0, 3000),
            )
            page2.save(chapter / "page-002.png")

            pending = [
                {
                    "id": 2,
                    "global_start": 3000,
                    "global_end": 9000,
                    "height": 6000,
                    "status": "failed",
                    "sources": [
                        "page-001.png",
                        "page-002.png",
                    ],
                }
            ]

            ok, msg, dest = rv.generate_candidate(
                manga,
                chapter,
                max_source_images=8,
                pending_segments=pending,
            )

            self.assertTrue(ok, msg)
            self.assertIsNotNone(dest)

            manifest = json.loads(
                (dest / "merge-review.json").read_text(
                    encoding="utf-8"
                )
            )

            self.assertEqual(
                manifest["scope"]["type"],
                "pending_segments",
            )
            self.assertEqual(
                manifest["scope"]["intervals"],
                [[3000, 9000]],
            )

            outputs = sorted(dest.glob("merged-*.png"))
            self.assertEqual(len(outputs), 1)

            # Boundaries permanecem no sistema GLOBAL do capítulo,
            # não em coordenadas locais 0..4000.
            self.assertEqual(
                manifest["boundaries"],
                [3000, 9000],
            )

            with Image.open(outputs[0]) as generated:
                actual = generated.convert("RGB")
                self.assertEqual(actual.size, (20, 6000))

                # Primeira metade vem do final de page-001.
                self.assertEqual(
                    actual.getpixel((10, 0)),
                    (0, 255, 0),
                )
                self.assertEqual(
                    actual.getpixel((10, 2999)),
                    (0, 255, 0),
                )

                # Segunda metade vem do início de page-002.
                self.assertEqual(
                    actual.getpixel((10, 3000)),
                    (0, 0, 255),
                )
                self.assertEqual(
                    actual.getpixel((10, 5999)),
                    (0, 0, 255),
                )


    def test_disjoint_pending_intervals_remain_independent(self):
        with tempfile.TemporaryDirectory(
            prefix="fominha_m5_disjoint_"
        ) as tmp:
            manga = Path(tmp) / "obra"
            chapter = manga / "IMG" / "6"
            chapter.mkdir(parents=True)

            colors = [
                (255, 0, 0),      # 0..4000       PASSED
                (0, 255, 0),      # 4000..8000    FAILED
                (0, 0, 255),      # 8000..12000   PASSED
                (255, 255, 0),    # 12000..16000  FAILED
                (255, 0, 255),    # 16000..20000  PASSED
            ]

            for index, color in enumerate(colors, 1):
                Image.new(
                    "RGB",
                    (20, 4000),
                    color,
                ).save(
                    chapter / f"page-{index:03d}.png"
                )

            pending = [
                {
                    "id": 2,
                    "global_start": 4000,
                    "global_end": 8000,
                    "height": 4000,
                    "status": "failed",
                    "sources": ["page-002.png"],
                },
                {
                    "id": 4,
                    "global_start": 12000,
                    "global_end": 16000,
                    "height": 4000,
                    "status": "failed",
                    "sources": ["page-004.png"],
                },
            ]

            ok, msg, dest = rv.generate_candidate(
                manga,
                chapter,
                max_source_images=8,
                pending_segments=pending,
            )

            self.assertTrue(ok, msg)
            self.assertIsNotNone(dest)

            manifest = json.loads(
                (dest / "merge-review.json").read_text(
                    encoding="utf-8"
                )
            )

            self.assertEqual(
                manifest["scope"]["type"],
                "pending_segments",
            )
            self.assertEqual(
                manifest["scope"]["intervals"],
                [
                    [4000, 8000],
                    [12000, 16000],
                ],
            )

            regions = manifest["regions"]

            self.assertEqual(len(regions), 2)

            self.assertEqual(
                [
                    [
                        int(region["global_start"]),
                        int(region["global_end"]),
                    ]
                    for region in regions
                ],
                [
                    [4000, 8000],
                    [12000, 16000],
                ],
            )

            self.assertEqual(
                [
                    region["boundaries"]
                    for region in regions
                ],
                [
                    [4000, 8000],
                    [12000, 16000],
                ],
            )

            # A região PASSED 8000..12000 não pode aparecer
            # dentro de nenhum escopo de Review.
            for region in regions:
                start = int(region["global_start"])
                end = int(region["global_end"])

                self.assertFalse(
                    start < 12000 and end > 8000
                    and not (
                        start == 4000 and end == 8000
                    )
                )

            outputs = sorted(dest.glob("merged-*.png"))
            self.assertEqual(len(outputs), 2)

            with Image.open(outputs[0]) as im:
                actual = im.convert("RGB")
                self.assertEqual(actual.size, (20, 4000))
                self.assertEqual(
                    actual.getpixel((10, 2000)),
                    (0, 255, 0),
                )

            with Image.open(outputs[1]) as im:
                actual = im.convert("RGB")
                self.assertEqual(actual.size, (20, 4000))
                self.assertEqual(
                    actual.getpixel((10, 2000)),
                    (255, 255, 0),
                )


    def test_scoped_review_accepts_terminal_remainder_within_review_max(self):
        with tempfile.TemporaryDirectory(
            prefix="fominha_m5_review_tail_"
        ) as tmp:
            manga = Path(tmp) / "obra"
            chapter = manga / "IMG" / "6"
            chapter.mkdir(parents=True)

            # Replica a geometria relevante do FAILED real:
            #
            # total scoped = 16731
            # corte branco seguro ~= 4396
            # restante final = 12335
            #
            # 12335 > normal_max (12000)
            # 12335 <= review_max (13000)
            #
            # Portanto o fim natural do pending deve ser aceito como
            # término do último merge, sem exigir um novo corte.

            image = Image.new(
                "RGB",
                (20, 16731),
                (0, 0, 0),
            )

            # Faixa branca de 242px centrada em 4396.
            image.paste(
                Image.new(
                    "RGB",
                    (20, 242),
                    (255, 255, 255),
                ),
                (0, 4275),
            )

            image.save(chapter / "page-001.png")

            pending = [
                {
                    "id": 9,
                    "global_start": 0,
                    "global_end": 16731,
                    "height": 16731,
                    "status": "failed",
                    "sources": ["page-001.png"],
                }
            ]

            ok, msg, dest = rv.generate_candidate(
                manga,
                chapter,
                max_source_images=8,
                pending_segments=pending,
            )

            self.assertTrue(ok, msg)
            self.assertIsNotNone(dest)

            manifest = json.loads(
                (dest / "merge-review.json").read_text(
                    encoding="utf-8"
                )
            )

            regions = manifest["regions"]
            self.assertEqual(len(regions), 1)

            bounds = regions[0]["boundaries"]

            self.assertEqual(bounds[0], 0)
            self.assertEqual(bounds[-1], 16731)
            self.assertEqual(len(bounds), 3)

            first_chunk = bounds[1] - bounds[0]
            final_chunk = bounds[2] - bounds[1]

            self.assertLessEqual(
                first_chunk,
                rv.REVIEW_MAX,
            )

            self.assertGreater(
                final_chunk,
                12000,
            )

            self.assertLessEqual(
                final_chunk,
                rv.REVIEW_MAX,
            )

            outputs = [
                dest / name
                for name in regions[0]["outputs"]
            ]

            self.assertEqual(len(outputs), 2)

            heights = []

            for output in outputs:
                with Image.open(output) as generated:
                    heights.append(generated.height)

            self.assertEqual(
                heights,
                [
                    first_chunk,
                    final_chunk,
                ],
            )

            self.assertEqual(
                sum(heights),
                16731,
            )


    def test_source_limit_uses_supplied_uniform_candidates_without_pages(self):
        infos = []

        for index in range(10):
            start = index * 1000
            end = start + 1000

            infos.append(
                v3.PageInfo(
                    path=Path(f"page-{index + 1:03d}.png"),
                    width=20,
                    height=1000,
                    global_start=start,
                    global_end=end,
                )
            )

        uniform_candidates = [
            {
                "center": 3500,
                "band_height": 18,
                "uniform_std": 0.0,
                "edge_mean": 0.0,
                "review_strategy": "uniform_color_safe_band",
            },
            {
                "center": 6800,
                "band_height": 18,
                "uniform_std": 0.0,
                "edge_mean": 0.0,
                "review_strategy": "uniform_color_safe_band",
            },
        ]

        cuts, inserted, error = rv._enforce_source_limit(
            [],
            infos,
            [],
            10000,
            4,
            pages=None,
            uniform_candidates=uniform_candidates,
        )

        self.assertIsNone(error)

        centers = [
            int(item["center"])
            for item in cuts
        ]

        self.assertEqual(
            centers,
            [3500, 6800],
        )

        self.assertEqual(
            [
                int(item["center"])
                for item in inserted
            ],
            [3500, 6800],
        )

        bounds = [0] + centers + [10000]

        source_counts = []

        for start, end in zip(bounds, bounds[1:]):
            sources = rv._segment_sources(
                infos,
                start,
                end,
            )
            source_counts.append(len(sources))

        self.assertEqual(
            source_counts,
            [4, 4, 4],
        )

        self.assertTrue(
            all(
                item.get("review_strategy")
                == "uniform_color_safe_band"
                for item in inserted
            )
        )


    def test_processing_web_passes_level2_pending_segments_to_review(self):
        import tempfile
        from types import SimpleNamespace
        from unittest.mock import patch

        from interface_web import processing_web as pw

        with tempfile.TemporaryDirectory(
            prefix="fominha_m5_bridge_"
        ) as tmp:
            root = Path(tmp)
            manga = root / "obra"
            chapter = manga / "IMG" / "6"
            chapter.mkdir(parents=True)

            pending = [
                {
                    "id": 9,
                    "status": "failed",
                    "global_start": 56853,
                    "global_end": 73584,
                    "height": 16731,
                }
            ]

            failure = {
                "status": "partial",
                "level2_status": "validated",
                "partition": {
                    "status": "partial",
                    "resolved_segments": [
                        {
                            "id": 8,
                            "status": "passed",
                            "global_start": 49842,
                            "global_end": 56853,
                        }
                    ],
                    "pending_segments": pending,
                },
            }

            job = SimpleNamespace(
                message="",
                progress=0,
            )

            captured = {}

            class FakeReview:
                def generate_candidate(
                    self,
                    manga_arg,
                    chapter_arg,
                    max_source_images=8,
                    pending_segments=None,
                ):
                    captured["manga"] = manga_arg
                    captured["chapter"] = chapter_arg
                    captured["max_source_images"] = max_source_images
                    captured["pending_segments"] = pending_segments

                    return (
                        True,
                        "ok",
                        manga_arg
                        / "FLUXO_SECUNDARIO"
                        / "MERGE_REVIEW"
                        / chapter_arg.name,
                    )

            with patch.object(
                pw,
                "reviewmod",
                return_value=FakeReview(),
            ), patch.object(
                pw,
                "read_merge_failure",
                return_value=failure,
            ):
                result = pw.do_review_generate(
                    job,
                    manga,
                    [chapter],
                    max_source_images=8,
                )

            self.assertEqual(
                captured.get("pending_segments"),
                pending,
            )

            self.assertEqual(
                captured.get("max_source_images"),
                8,
            )

            self.assertEqual(
                captured.get("chapter"),
                chapter,
            )

            self.assertEqual(
                len(result),
                1,
            )

            self.assertEqual(
                result[0]["status"],
                "ok",
            )


    def test_processing_web_does_not_scope_review_before_level2_validation(self):
        import tempfile
        from types import SimpleNamespace
        from unittest.mock import patch

        from interface_web import processing_web as pw

        with tempfile.TemporaryDirectory(
            prefix="fominha_m5_bridge_gate_"
        ) as tmp:
            root = Path(tmp)
            manga = root / "obra"
            chapter = manga / "IMG" / "6"
            chapter.mkdir(parents=True)

            pending = [
                {
                    "id": 9,
                    "status": "failed",
                    "global_start": 56853,
                    "global_end": 73584,
                    "height": 16731,
                }
            ]

            failure = {
                "status": "partial",
                # Importante:
                # NÃO existe level2_status="validated".
                "partition": {
                    "status": "partial",
                    "level2_validated": False,
                    "resolved_segments": [
                        {
                            "id": 8,
                            "status": "passed",
                            "global_start": 49842,
                            "global_end": 56853,
                        }
                    ],
                    "pending_segments": pending,
                },
            }

            job = SimpleNamespace(
                message="",
                progress=0,
            )

            captured = {}

            class FakeReview:
                def generate_candidate(
                    self,
                    manga_arg,
                    chapter_arg,
                    max_source_images=8,
                    pending_segments=None,
                ):
                    captured["pending_segments"] = pending_segments
                    captured["max_source_images"] = max_source_images

                    return (
                        True,
                        "ok",
                        manga_arg
                        / "FLUXO_SECUNDARIO"
                        / "MERGE_REVIEW"
                        / chapter_arg.name,
                    )

            with patch.object(
                pw,
                "reviewmod",
                return_value=FakeReview(),
            ), patch.object(
                pw,
                "read_merge_failure",
                return_value=failure,
            ):
                result = pw.do_review_generate(
                    job,
                    manga,
                    [chapter],
                    max_source_images=8,
                )

            self.assertIsNone(
                captured.get("pending_segments"),
                "Review não pode entrar em modo scoped "
                "antes da validação do Level II.",
            )

            self.assertEqual(
                captured.get("max_source_images"),
                8,
            )

            self.assertEqual(
                len(result),
                1,
            )

            self.assertEqual(
                result[0]["status"],
                "ok",
            )



    def test_uniform_detector_rejects_center_only_uniform_strip(self):
        """
        Uma faixa uniforme apenas no miolo da imagem não é segura.

        Reproduz a classe de falso positivo observada no capítulo 6:
        o detector central vê cor uniforme, mas esquerda/direita possuem
        conteúdo estruturalmente diferente.
        """
        import tempfile
        from pathlib import Path

        from PIL import Image, ImageDraw

        from processamento.unificacao_imagens import image_stitcher as v3
        from processamento.unificacao_imagens import image_stitcher_review as rv

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            page = root / "page-001.png"

            width = 720
            height = 120

            image = Image.new(
                "RGB",
                (width, height),
                (237, 239, 243),
            )

            draw = ImageDraw.Draw(image)

            # Fora da amostra central de 256 px, introduzimos regiões
            # estruturalmente muito diferentes.
            center_width = 256
            center_x0 = (width - center_width) // 2
            center_x1 = center_x0 + center_width

            draw.rectangle(
                (0, 0, center_x0 - 1, height - 1),
                fill=(250, 250, 250),
            )
            draw.rectangle(
                (center_x1, 0, width - 1, height - 1),
                fill=(0, 0, 0),
            )

            image.save(page, "PNG")

            pages = [page]

            infos, _, _, _ = v3.analyze_chapter(
                pages,
                sample_width=v3.DEFAULT_SAMPLE_WIDTH,
                light_threshold=v3.DEFAULT_LIGHT_THRESHOLD,
                white_ratio_threshold=v3.DEFAULT_WHITE_RATIO,
            )

            candidates = rv._uniform_band_candidates(
                pages,
                infos,
            )

            self.assertEqual(
                candidates,
                [],
                "Faixa uniforme apenas no centro não pode ser "
                "considerada segura para corte.",
            )

    def test_uniform_detector_accepts_full_width_uniform_strip(self):
        """
        Uma faixa realmente uniforme em toda a largura continua elegível.

        Protege o comportamento necessário para casos como o corte
        full-width preto observado no capítulo 6.
        """
        import tempfile
        from pathlib import Path

        from PIL import Image

        from processamento.unificacao_imagens import image_stitcher as v3
        from processamento.unificacao_imagens import image_stitcher_review as rv

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            page = root / "page-001.png"

            image = Image.new(
                "RGB",
                (720, 120),
                (0, 0, 0),
            )
            image.save(page, "PNG")

            pages = [page]

            infos, _, _, _ = v3.analyze_chapter(
                pages,
                sample_width=v3.DEFAULT_SAMPLE_WIDTH,
                light_threshold=v3.DEFAULT_LIGHT_THRESHOLD,
                white_ratio_threshold=v3.DEFAULT_WHITE_RATIO,
            )

            candidates = rv._uniform_band_candidates(
                pages,
                infos,
            )

            self.assertGreater(
                len(candidates),
                0,
                "Faixa uniforme em toda a largura deve continuar elegível.",
            )

if __name__ == "__main__":
    unittest.main()
