import tempfile
import unittest
from pathlib import Path

from PIL import Image

from processamento.unificacao_imagens.image_stitcher import merge_chapter, merge_output_dir


class ImageStitcherSafetyTests(unittest.TestCase):
    def test_oversized_chunk_is_rejected_before_render(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            chapter = root / "output" / "comix" / "Obra" / "IMG" / "1"
            chapter.mkdir(parents=True)

            for index in (1, 2):
                image = Image.new("RGB", (64, 7000), "black")
                image.save(chapter / f"page-{index:03d}.png", "PNG")

            output_dir = merge_output_dir(chapter)

            with self.assertRaisesRegex(
                RuntimeError,
                r"Merge interrompido com segurança.*12,000 px",
            ):
                merge_chapter(chapter)

            self.assertFalse(
                output_dir.exists(),
                "A barreira deve falhar antes de criar a pasta de saída.",
            )


if __name__ == "__main__":
    unittest.main()
