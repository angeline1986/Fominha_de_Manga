import json
import shutil
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from processamento.unificacao_imagens import image_stitcher as v3
from processamento.unificacao_imagens import image_stitcher_review as review


class ImageStitcherReviewTests(unittest.TestCase):

    def _make_page(self, path: Path, *, width=120, height=4000, white_bands=None, fill="black"):
        image = Image.new("RGB", (width, height), fill)
        if white_bands:
            draw = ImageDraw.Draw(image)
            for top, bottom in white_bands:
                draw.rectangle((0, top, width - 1, bottom - 1), fill="white")
        image.save(path)

    def _analyze(self, pages):
        return v3.analyze_chapter(
            pages,
            sample_width=v3.DEFAULT_SAMPLE_WIDTH,
            light_threshold=v3.DEFAULT_LIGHT_THRESHOLD,
            white_ratio_threshold=v3.DEFAULT_WHITE_RATIO,
        )

    def test_source_limit_prefers_white_band_before_uniform(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            pages = []
            for i in range(1, 6):
                p = root / f"page-{i:03d}.png"
                self._make_page(p, height=2000)
                pages.append(p)

            # Centro global ~5000, dentro da janela válida 3000..7000.
            with Image.open(pages[2]) as im:
                image = im.convert("RGB")
            draw = ImageDraw.Draw(image)
            draw.rectangle((0, 900, image.width - 1, 1100), fill="white")
            image.save(pages[2])

            infos, bands, total, _ = self._analyze(pages)

            cuts, inserted, error = review._enforce_source_limit(
                [],
                infos,
                bands,
                total,
                max_source_images=4,
                pages=pages,
            )

            self.assertIsNone(error)
            self.assertTrue(inserted)
            self.assertEqual(
                inserted[0].get("review_strategy"),
                "source_limit_safe_white_band",
            )

    def test_uniform_band_is_fallback_when_white_band_is_unavailable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            pages = []
            for i in range(1, 6):
                p = root / f"page-{i:03d}.png"

                # Cor uniforme não branca.
                image = Image.new("RGB", (120, 2000), (80, 80, 80))
                image.save(p)
                pages.append(p)

            infos, bands, total, _ = self._analyze(pages)

            cuts, inserted, error = review._enforce_source_limit(
                [],
                infos,
                bands,
                total,
                max_source_images=4,
                pages=pages,
            )

            self.assertIsNone(error)
            self.assertTrue(inserted)
            self.assertEqual(
                inserted[0].get("review_strategy"),
                "uniform_color_safe_band",
            )

    def test_source_limit_fails_safely_without_valid_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            pages = []

            for i in range(1, 10):
                p = root / f"page-{i:03d}.png"

                # Imagem propositalmente não uniforme e sem faixa branca.
                image = Image.new("RGB", (120, 1000), "black")
                draw = ImageDraw.Draw(image)

                for y in range(0, 1000, 20):
                    if (y // 20) % 2:
                        draw.rectangle((0, y, 119, min(y + 9, 999)), fill=(180, 30, 30))
                    else:
                        draw.rectangle((0, y, 119, min(y + 9, 999)), fill=(20, 160, 50))

                image.save(p)
                pages.append(p)

            infos, bands, total, _ = self._analyze(pages)

            cuts, inserted, error = review._enforce_source_limit(
                [],
                infos,
                bands,
                total,
                max_source_images=4,
                pages=pages,
            )

            self.assertIsNone(cuts)
            self.assertIsNotNone(error)

            # Segurança: nenhuma estratégia de corte forçado deve aparecer.
            self.assertFalse(
                any(
                    "forced" in str(item.get("review_strategy", "")).lower()
                    for item in inserted
                )
            )

    def test_chapter_6_baseline_is_complete_limited_and_deterministic(self):
        repo = Path(__file__).resolve().parents[2]

        source_chapter = (
            repo
            / "download"
            / "mangago_downloader"
            / "output"
            / "comix"
            / "Emergency_Youth Record Book"
            / "IMG"
            / "6"
        )

        if not source_chapter.is_dir():
            self.skipTest("Capítulo 6 real não está disponível neste ambiente.")

        pages = sorted(source_chapter.glob("*.png"))

        if len(pages) != 143:
            self.skipTest(
                f"Dataset esperado possui 143 PNGs; encontrados {len(pages)}."
            )

        snapshots = []

        for run in range(2):
            with tempfile.TemporaryDirectory() as tmp:
                sandbox = Path(tmp)
                manga = sandbox / "Emergency_Youth Record Book"
                img = manga / "IMG"
                chapter = img / "6"

                img.mkdir(parents=True)
                chapter.symlink_to(source_chapter, target_is_directory=True)

                ok, msg, dest = review.generate_candidate(
                    manga,
                    chapter,
                    max_source_images=8,
                )

                self.assertTrue(ok, msg)
                self.assertIsNotNone(dest)

                dest = Path(dest)
                manifest_path = dest / "merge-review.json"

                self.assertTrue(manifest_path.is_file())

                manifest = json.loads(
                    manifest_path.read_text(encoding="utf-8")
                )

                outputs = sorted(dest.glob("merged-*.png"))

                self.assertEqual(len(outputs), 30)

                total_height = 0
                for p in outputs:
                    with Image.open(p) as im:
                        total_height += im.height

                self.assertEqual(total_height, 119971)

                boundaries = manifest.get("boundaries") or []

                self.assertEqual(boundaries[0], 0)
                self.assertEqual(boundaries[-1], 119971)
                self.assertEqual(len(boundaries), len(outputs) + 1)

                infos, _, _, _ = self._analyze(pages)

                for start, end in zip(boundaries, boundaries[1:]):
                    sources = review._segment_sources(infos, start, end)
                    self.assertLessEqual(
                        len(sources),
                        8,
                        f"Segmento {start}->{end} usa {len(sources)} originais",
                    )

                output_sizes = []
                for p in outputs:
                    with Image.open(p) as im:
                        output_sizes.append((p.name, im.size))

                snapshots.append({
                    "boundaries": boundaries,
                    "cuts": manifest.get("cuts") or [],
                    "proposal": manifest.get("proposal") or [],
                    "outputs": output_sizes,
                })

        self.assertEqual(
            snapshots[0]["boundaries"],
            snapshots[1]["boundaries"],
        )

        self.assertEqual(
            snapshots[0]["cuts"],
            snapshots[1]["cuts"],
        )

        self.assertEqual(
            snapshots[0]["proposal"],
            snapshots[1]["proposal"],
        )

        self.assertEqual(
            snapshots[0]["outputs"],
            snapshots[1]["outputs"],
        )


if __name__ == "__main__":
    unittest.main()
