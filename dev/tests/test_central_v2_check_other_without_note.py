"""A Check selection of Outro remains available in Laboratory without a note."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from urllib.parse import urlencode
from unittest.mock import patch

from PIL import Image

from central_v2.backend.routes.router import dispatch_get, dispatch_post
from central_v2.backend.orchestration.textoff_merged.residue_occurrences import validate_occurrences


class CheckOtherWithoutNoteTests(unittest.TestCase):
    def test_check_save_and_laboratory_listing(self):
        with TemporaryDirectory() as temporary:
            output = Path(temporary)
            image = output / "ridi/obra/IMG/1/page-001.png"
            image.parent.mkdir(parents=True)
            Image.new("RGB", (64, 32), "white").save(image)
            pair = [{"name": image.name, "before": image, "after": image}]
            context = {"provider": "ridi", "manga": "obra", "chapter": "1",
                       "page": image.name, "step": "1", "scope": "check"}
            with patch("central_v2.backend.routes.textoff_residue_occurrences.comparison_pairs",
                       return_value=pair), patch(
                "central_v2.backend.routes.auto_cleaner_check_special_treatments.rebuild_after_check",
                return_value=None,
            ):
                opened = dispatch_get("/api/textoff/residue-occurrences?" + urlencode(context), output)
                self.assertEqual(opened.status, 200)
                snapshot = json.loads(opened.body)["source_snapshot"]
                saved = dispatch_post("/api/textoff/residue-occurrences", {
                    **context, "source_snapshot": snapshot,
                    "pages": [{"page": image.name, "occurrences": [{
                        "id": "other-1", "number": 1, "type": "outro", "note": None,
                        "box_normalized": {"left": .1, "top": .1, "width": .2, "height": .2},
                    }]}],
                }, output)
            self.assertEqual(saved.status, 200, saved.body)
            self.assertIsNone(json.loads(saved.body)["pages"][0]["occurrences"][0]["observacao"])
            listed = dispatch_get("/api/textoff/laboratorio/pages?"
                                  "provider=ridi&manga=obra&source=check", output)
            self.assertEqual(listed.status, 200, listed.body)
            self.assertEqual([row["name"] for row in json.loads(listed.body)["chapters"]["1"]],
                             ["page-001.png"])

    def test_catalog_outside_check_still_requires_description(self):
        row = {"id": "other-1", "number": 1, "type": "outro", "note": None,
               "box_normalized": {"left": .1, "top": .1, "width": .2, "height": .2}}
        with self.assertRaisesRegex(ValueError, "Descreva o defeito"):
            validate_occurrences([row], 64, 32)


if __name__ == "__main__":
    unittest.main()
