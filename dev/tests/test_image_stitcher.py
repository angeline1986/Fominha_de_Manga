import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from processamento.unificacao_imagens.image_stitcher import (
    DEFAULT_MIN_WHITE_BAND,
    WhiteBand,
    choose_cuts,
    is_chapter_merged,
    merge_chapter,
    merge_output_dir,
)


class ImageStitcherTests(unittest.TestCase):
    def _chapter(self, root: Path) -> Path:
        chapter = root / "output" / "comix" / "Obra" / "IMG" / "28"
        chapter.mkdir(parents=True)
        return chapter

    def _page(self, path: Path, *, width: int = 120, height: int = 4000, white_band=None):
        image = Image.new("RGB", (width, height), "black")
        if white_band:
            draw = ImageDraw.Draw(image)
            top, bottom = white_band
            draw.rectangle((0, top, width - 1, bottom - 1), fill="white")
        image.save(path)

    def test_short_band_is_rejected(self):
        cuts, decisions = choose_cuts(
            16000,
            [WhiteBand(6900, 6972, 72, 1.0), WhiteBand(8000, 8200, 200, 1.0)],
            target_height=7000,
            search_before=1800,
            search_after=2500,
            min_chunk_height=3000,
            min_white_band=DEFAULT_MIN_WHITE_BAND,
            max_chunk_height=12000,
        )
        self.assertEqual(len(cuts), 1)
        self.assertEqual(cuts[0]["band_height"], 200)
        self.assertTrue(
            any(item.get("reason") == "white_band_too_short" for item in decisions)
        )

    def test_merge_uses_official_secondary_flow_and_preserves_coverage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            chapter = self._chapter(root)
            self._page(chapter / "page-001.png", white_band=(3800, 4000))
            self._page(chapter / "page-002.png", white_band=(3000, 3250))
            self._page(chapter / "page-003.png")

            result = merge_chapter(
                chapter,
                target_height=6500,
                search_before=2500,
                search_after=2500,
                min_chunk_height=2500,
                max_chunk_height=10000,
            )

            expected_dir = root / "output" / "comix" / "Obra" / "FLUXO_SECUNDARIO" / "02_MERGE" / "28"
            self.assertEqual(result.output_dir.resolve(), expected_dir.resolve())
            self.assertTrue(result.manifest_path.is_file())
            self.assertTrue(is_chapter_merged(chapter))
            self.assertTrue((chapter / "page-001.png").is_file())
            self.assertTrue((chapter / "page-002.png").is_file())
            self.assertTrue((chapter / "page-003.png").is_file())

            manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["algorithm"], "whitespace_v3")
            self.assertEqual(manifest["source_pages"], 3)
            self.assertEqual(manifest["parameters"]["min_white_band"], 150)
            self.assertTrue(manifest["safety"]["all_source_pixels_preserved_in_order"])
            self.assertFalse(manifest["safety"]["source_files_modified"])
            self.assertEqual(manifest["outputs"][0]["global_start"], 0)
            self.assertEqual(
                manifest["outputs"][-1]["global_end"],
                manifest["source_total_height"],
            )

    def test_existing_merge_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            chapter = self._chapter(Path(tmp))
            self._page(chapter / "page-001.png")
            output = merge_output_dir(chapter)
            output.mkdir(parents=True)
            (output / "keep.txt").write_text("existing", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                merge_chapter(chapter)
            self.assertEqual((output / "keep.txt").read_text(encoding="utf-8"), "existing")


if __name__ == "__main__":
    unittest.main()
