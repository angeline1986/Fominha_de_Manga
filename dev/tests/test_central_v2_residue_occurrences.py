"""Human residue catalog persistence is page/step scoped and contained."""
import json
from pathlib import Path
import tempfile
import unittest
from urllib.parse import urlencode
from unittest.mock import patch

from PIL import Image

from central_v2.backend.routes.router import dispatch_get, dispatch_post


class ResidueOccurrenceRouteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manga = self.root / "ridi" / "obra"
        self.manga.mkdir(parents=True)
        self.after = self.root / "clean.png"
        Image.new("RGB", (64, 32), "white").save(self.after)
        self.pairs = [{"name": name, "before": self.after, "after": self.after}
                      for name in ("page-A.png", "page-B.png")]
        self.patch = patch("central_v2.backend.routes.textoff_residue_occurrences.comparison_pairs",
                            return_value=self.pairs)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def context(self, page="page-A.png", step="1"):
        return {"provider": "ridi", "manga": "obra", "chapter": "12", "page": page, "step": step}

    def occurrence(self, **changes):
        item = {"id": "occ-1", "number": 1, "type": "residuo_transparencia", "note": "ignored",
                "box_normalized": {"left": .25, "top": .5, "width": .5, "height": .25}}
        item.update(changes)
        return item

    def post(self, context=None, occurrences=None):
        payload = {**(context or self.context()), "occurrences": occurrences if occurrences is not None else [self.occurrence()]}
        response = dispatch_post("/api/textoff/residue-occurrences", payload, self.root)
        return response, json.loads(response.body)

    def get(self, context=None):
        response = dispatch_get("/api/textoff/residue-occurrences?" + urlencode(context or self.context()), self.root)
        return response, json.loads(response.body)

    def test_get_without_manifest_returns_empty_success_and_post_writes_natural_pixels(self):
        response, data = self.get()
        self.assertEqual(response.status, 200)
        self.assertEqual(data["occurrences"], [])
        self.assertFalse(data["cataloged"])
        response, saved = self.post()
        self.assertEqual(response.status, 200)
        self.assertEqual(saved["occurrences"][0]["box_pixels"], {"x": 16, "y": 16, "width": 32, "height": 8})
        manifest = self.manga / "FLUXO_SECUNDARIO/04_TEXTO_OFF/RESIDUE_OCCURRENCES/12/residue-occurrences-manifest.json"
        self.assertTrue(manifest.is_file())
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        self.assertEqual(payload["schema"], "textoff_residue_occurrence_manifest_v1")
        self.assertEqual(payload["pages"]["page-A.png"]["steps"]["1"]["total_ocorrencias"], 1)

    def test_post_preserves_pages_and_the_same_page_in_other_steps(self):
        self.post()
        self.post(self.context("page-B.png"), [self.occurrence(id="occ-b")])
        self.post(self.context(step="2"), [self.occurrence(id="occ-step-2")])
        _, page_a = self.get(self.context())
        _, step_two = self.get(self.context(step="2"))
        _, page_b = self.get(self.context("page-B.png"))
        self.assertEqual(page_a["occurrences"][0]["id"], "occ-1")
        self.assertEqual(step_two["occurrences"][0]["id"], "occ-step-2")
        self.assertEqual(page_b["occurrences"][0]["id"], "occ-b")

    def test_page_and_context_must_match_authorized_comparison_pairs(self):
        for context in (self.context("../page-A.png"), self.context("nested/page-A.png"),
                        self.context("page-A.png", step="9"), {"provider": "ridi"}):
            response, _ = self.post(context, [self.occurrence()])
            self.assertEqual(response.status, 400)
        response, _ = self.post(self.context(r"C:\\page-A.png"), [self.occurrence()])
        self.assertEqual(response.status, 400)

    def test_post_rejects_unknown_type_invalid_box_and_missing_other_note(self):
        invalid = [([self.occurrence(type="unknown")], "Tipo"),
                   ([self.occurrence(box_normalized={"left": .8, "top": 0, "width": .3, "height": .2})], "limites"),
                   ([self.occurrence(type="outro", note="  ")], "Descreva")]
        for rows, expected in invalid:
            response, data = self.post(occurrences=rows)
            self.assertEqual(response.status, 400)
            self.assertIn(expected.lower(), data["error"].lower())

    def test_post_empty_clears_only_current_page_and_step_and_returns_zero(self):
        self.post()
        self.post(self.context("page-B.png"), [self.occurrence(id="occ-b")])
        self.post(self.context(step="2"), [self.occurrence(id="occ-step-2")])

        response, data = self.post(occurrences=[])
        self.assertEqual(response.status, 200)
        self.assertEqual(data["total_occurrences"], 0)
        self.assertEqual(data["occurrences"], [])
        _, current = self.get(self.context())
        _, page_b = self.get(self.context("page-B.png"))
        _, step_two = self.get(self.context(step="2"))
        self.assertEqual(current["occurrences"], [])
        self.assertEqual(page_b["occurrences"][0]["id"], "occ-b")
        self.assertEqual(step_two["occurrences"][0]["id"], "occ-step-2")
        manifest = self.manga / "FLUXO_SECUNDARIO/04_TEXTO_OFF/RESIDUE_OCCURRENCES/12/residue-occurrences-manifest.json"
        self.assertTrue(manifest.is_file())


if __name__ == "__main__":
    unittest.main()
