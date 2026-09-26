import tempfile
import unittest
from pathlib import Path

from central_v2.backend.state.manga_state import (
    build_structural_state,
    resolve_manga,
)


class CentralV2MangaStateTest(unittest.TestCase):
    def test_build_structural_state_preserves_legacy_discovery_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "output"
            manga = output / "comix" / "Smoke Manga"
            img = manga / "IMG"

            chapter_10 = img / "10"
            chapter_2 = img / "2"
            chapter_1 = img / "1"
            inactive = img / "3"

            for chapter in (chapter_10, chapter_2, chapter_1, inactive):
                chapter.mkdir(parents=True)

            (chapter_10 / "page-001.webp").write_bytes(b"x")
            (chapter_2 / "page-001.JPG").write_bytes(b"x")
            (chapter_1 / "page-001.png").write_bytes(b"x")

            # Não torna o capítulo ativo.
            (inactive / "page-001_old.png").write_bytes(b"x")
            (inactive / "notes.txt").write_text("ignore")

            state = build_structural_state(
                output,
                "comix",
                "Smoke Manga",
            )

            self.assertEqual(state["provider"], "comix")
            self.assertEqual(state["manga"], "Smoke Manga")
            self.assertEqual(state["chapters"], ["1", "2", "10"])
            self.assertEqual(state["summary"]["chapters"], 3)

    def test_resolve_manga_rejects_invalid_provider_and_path_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "output"
            (output / "comix" / "Smoke Manga").mkdir(parents=True)

            with self.assertRaisesRegex(ValueError, "Provider inválido"):
                resolve_manga(output, "invalid", "Smoke Manga")

            with self.assertRaisesRegex(ValueError, "Obra inválida"):
                resolve_manga(output, "comix", "../outside")


if __name__ == "__main__":
    unittest.main()
