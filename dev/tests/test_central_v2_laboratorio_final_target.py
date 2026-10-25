"""Final targets from selected files must be unique or explicitly identified."""
import json
from pathlib import Path
import tempfile
import unittest

from central_v2.backend.orchestration.textoff_merged.laboratorio_final_target import final_target


class FinalTargetTests(unittest.TestCase):
    def test_ambiguous_filename_does_not_choose_an_arbitrary_chapter(self):
        with tempfile.TemporaryDirectory() as temporary:
            manga = Path(temporary) / "ridi/obra"
            root = manga / "FLUXO_SECUNDARIO/04_TEXTO_OFF/07_CONSOLIDADO_FINAL"
            for chapter in ("1", "2"):
                manifest = root / chapter / "json/final-manifest.json"
                manifest.parent.mkdir(parents=True)
                manifest.write_text(json.dumps({"provider": "ridi", "manga": "obra",
                    "chapter": chapter, "pages": {"page.png": {}}}), encoding="utf-8")
            source_path = manga / "FLUXO_SECUNDARIO/04_TEXTO_OFF/04_AUTO_CLEANER_CHECK/3/images/page.png"
            with self.assertRaisesRegex(ValueError, "mais de um capítulo"):
                final_target(manga, source_path, {"chapter": "images", "filename": "page.png"})
            identified = manga / "FLUXO_SECUNDARIO/04_TEXTO_OFF/04_AUTO_CLEANER_CHECK/1/images/page.png"
            self.assertEqual(final_target(manga, identified,
                {"chapter": "images", "filename": "page.png"}), ("1", "page.png"))
            self.assertEqual(final_target(manga, manga / "IMG/1/page.png",
                {"chapter": "1", "filename": "page.png"}), ("1", "page.png"))


if __name__ == "__main__":
    unittest.main()
