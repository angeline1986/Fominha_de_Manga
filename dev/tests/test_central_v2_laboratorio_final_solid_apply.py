"""Legacy Sólidos previews can target the verified final chapter without a rerun."""
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from central_v2.backend.orchestration.textoff_special.artifacts import sha256
from central_v2.backend.orchestration.textoff_merged.final_consolidated import final_manifest_path
from central_v2.backend.routes.router import dispatch_post


class SolidApplyTests(unittest.TestCase):
    def test_legacy_clean_preview_proposes_and_applies_only_chapter_five(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            manga = output / "comix/obra"
            (manga / "IMG").mkdir(parents=True)
            source = (manga / "FLUXO_SECUNDARIO/04_TEXTO_OFF/01_AUTO_CLEANER"
                      / "5/clean/page_clean.png")
            source.parent.mkdir(parents=True)
            Image.new("RGB", (20, 30), "white").save(source)
            run_id = "a" * 32
            preview = output / "_laboratorio_solidos_previews" / run_id / "preview.png"
            preview.parent.mkdir(parents=True)
            Image.new("RGB", (20, 30), "green").save(preview)
            (preview.parent / "manifest.json").write_text(json.dumps({
                "schema": "laboratorio_solidos_preview_v1", "preview_only": True,
                "provider": "comix", "manga": "obra", "chapter": "clean",
                "page": "page_clean.png", "source_sha256": sha256(source),
                "preview_sha256": sha256(preview)}))
            for chapter in ("3", "5"):
                manifest = final_manifest_path(manga, chapter)
                manifest.parent.mkdir(parents=True)
                image = manifest.parent.parent / "page.png"
                Image.new("RGB", (20, 30), "blue").save(image)
                manifest.write_text(json.dumps({
                    "schema": "textoff_consolidado_final_manifest_v1", "version": 1,
                    "provider": "comix", "manga": "obra", "chapter": chapter,
                    "source_intermediate_manifest_sha256": "baseline",
                    "pages": {"page.png": {"page": "page.png", "artifact": "page.png",
                        "sha256": sha256(image), "origin": "PINCEL_SUAVE"}},
                    "history": []}))
            payload = {"provider": "comix", "manga": "obra", "chapter": "clean",
                       "page": "page_clean.png", "treatment": "solidos", "run_id": run_id}
            other = (final_manifest_path(manga, "3").parent.parent / "page.png").read_bytes()
            response = dispatch_post("/api/textoff/laboratorio/final/proposal", payload, output)
            self.assertEqual(response.status, 200, response.body)
            proposal = json.loads(response.body)
            self.assertEqual((proposal["chapter"], proposal["page"]), ("5", "page.png"))
            applied = dispatch_post("/api/textoff/laboratorio/final/apply", {
                **payload, "chapter": "5", "page": "page.png",
                "version": proposal["version"], "confirmed": True}, output)
            self.assertEqual(applied.status, 200, applied.body)
            self.assertEqual(sha256(final_manifest_path(manga, "5").parent.parent
                                    / "page.png"), sha256(preview))
            self.assertEqual((final_manifest_path(manga, "3").parent.parent
                              / "page.png").read_bytes(), other)


if __name__ == "__main__":
    unittest.main()
