"""Final targets from selected files must be unique or explicitly identified."""
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from central_v2.backend.orchestration.textoff_special.artifacts import sha256
from central_v2.backend.orchestration.textoff_merged.laboratorio_final_solid_source import solid_target
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
            self.assertEqual(final_target(manga, identified,
                {"chapter": "1", "filename": "page.png"}), ("1", "page.png"))
            self.assertEqual(final_target(manga, manga / "IMG/1/page.png",
                {"chapter": "1", "filename": "page.png"}), ("1", "page.png"))
            glass = manga / "FLUXO_SECUNDARIO/04_TEXTO_OFF/TO_MERGED_NIVEL_II/1/clean/page_clean.png"
            self.assertEqual(final_target(manga, glass,
                {"chapter": "1", "filename": "page_clean.png"}), ("1", "page.png"))

    def test_legacy_solids_uses_verified_source_hash_and_rejects_ambiguous_chapters(self):
        with tempfile.TemporaryDirectory() as temporary:
            manga = Path(temporary) / "comix/obra"
            final = manga / "FLUXO_SECUNDARIO/04_TEXTO_OFF/07_CONSOLIDADO_FINAL"
            for chapter in ("3", "5"):
                manifest = final / chapter / "json/final-manifest.json"
                manifest.parent.mkdir(parents=True)
                manifest.write_text(json.dumps({"provider": "comix", "manga": "obra",
                    "chapter": chapter, "pages": {"page.png": {}}}))
            sources = []
            for stage in ("01_AUTO_CLEANER", "TO_MERGED_NIVEL_I"):
                source = (manga / "FLUXO_SECUNDARIO/04_TEXTO_OFF" / stage
                          / "5/clean/page_clean.png")
                source.parent.mkdir(parents=True)
                Image.new("RGB", (8, 8), "white").save(source)
                sources.append(source)
            meta = {"chapter": "clean", "page": "page_clean.png",
                    "source_sha256": sha256(sources[0])}
            self.assertEqual(solid_target(manga, meta), ("5", "page.png"))
            another = (manga / "FLUXO_SECUNDARIO/04_TEXTO_OFF/01_AUTO_CLEANER"
                       / "3/clean/page_clean.png")
            another.parent.mkdir(parents=True)
            another.write_bytes(sources[0].read_bytes())
            with self.assertRaisesRegex(ValueError, "página final única"):
                solid_target(manga, meta)
            meta["source_path"] = str(sources[0].relative_to(manga))
            self.assertEqual(solid_target(manga, meta), ("5", "page.png"))
            Image.new("RGB", (8, 8), "black").save(sources[0])
            with self.assertRaisesRegex(ValueError, "mudou"):
                solid_target(manga, meta)


if __name__ == "__main__":
    unittest.main()
