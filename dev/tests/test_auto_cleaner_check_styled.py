"""Check classification option persists the stable styled-balloon type."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlencode
from unittest import TestCase
from unittest.mock import patch

from PIL import Image

from central_v2.backend.routes.router import dispatch_get, dispatch_post
from central_v2.backend.orchestration.textoff_merged.auto_cleaner_check_manifest import (
    manifest_path as check_path,
)
from central_v2.backend.orchestration.textoff_merged.special_treatments_manifest import (
    manifest_path as special_path,
)


class StyledBalloonCheckTests(TestCase):
    def test_manual_check_decision_keeps_roi_and_saves_stable_type(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            manga = root / "comix" / "Candy YumYum (Yaoi)"
            (manga / "IMG" / "1").mkdir(parents=True)
            image = root / "page.png"
            Image.new("RGB", (80, 60), "white").save(image)
            pair = {"name": "page.png", "before": image, "after": image}
            context = {"provider": "comix", "manga": manga.name, "chapter": "1",
                       "page": "page.png", "step": "1", "scope": "check"}
            with patch("central_v2.backend.routes.textoff_residue_occurrences.comparison_pairs",
                       return_value=[pair]):
                response = dispatch_get("/api/textoff/residue-occurrences?" +
                                        urlencode(context), root)
                opened = json.loads(response.body)
                roi = {"left": .25, "top": .2, "width": .3, "height": .25}
                decision = {"id": "styled-1", "number": 1, "type": "balao_estilizado",
                    "box_normalized": roi, "origin": "MANUAL", "origins": ["MANUAL"],
                    "source_references": [{"origin": "MANUAL", "selection": 1}]}
                payload = {**context, "source_snapshot": opened["source_snapshot"],
                    "pages": [{"page": "page.png", "occurrences": [decision]}]}
                saved = dispatch_post("/api/textoff/residue-occurrences", payload, root)
            self.assertEqual(saved.status, 200, saved.body)
            self.assertTrue(json.loads(saved.body)["special_treatments_updated"])
            manifest = manga / "FLUXO_SECUNDARIO/04_TEXTO_OFF/04_AUTO_CLEANER_CHECK/1/auto-cleaner-check-manifest.json"
            row = json.loads(manifest.read_text())["approved_occurrences"][0]
            self.assertEqual(row["tipo"], "balao_estilizado")
            self.assertEqual(row["box_normalized"], roi)
            self.assertEqual(row["box_pixels"], {"x": 20, "y": 12, "width": 24, "height": 15})
            self.assertEqual(row["source_references"], decision["source_references"])
            special = json.loads(special_path(manga, "1").read_text())
            self.assertEqual(special["treatments"]["estilizado"][0]["id"], "styled-1")

    def test_check_save_preserves_unchanged_result_and_execution_history(self):
        with TemporaryDirectory() as temporary:
            root, manga, image, context = self._context(Path(temporary))
            with patch("central_v2.backend.routes.textoff_residue_occurrences.comparison_pairs",
                       return_value=[{"name": "page.png", "before": image, "after": image}]):
                opened = json.loads(dispatch_get("/api/textoff/residue-occurrences?" +
                    urlencode(context), root).body)
                original = [self._decision("styled-1"),
                    self._decision("degrade-1", kind="residuo_degrade"),
                    self._decision("smooth-1", kind="residuo_gradiente")]
                saved = self._save_styled(root, context, opened, original)
                self.assertEqual(saved.status, 200)
                special_file = special_path(manga, "1")
                current = json.loads(special_file.read_text())
                for treatment in current["treatments"].values():
                    treatment[0].update(status="processed", result={
                        "run_id": "run-" + treatment[0]["id"], "output": "kept.png"})
                current["reexecution_history"] = [{"id": "history-1"}]
                special_file.write_text(json.dumps(current))
                reopened = json.loads(dispatch_get("/api/textoff/residue-occurrences?" +
                    urlencode(context), root).body)
                saved = self._save_styled(root, context, reopened,
                    [*original, self._decision("styled-2", .6)])
            self.assertEqual(saved.status, 200, saved.body)
            refreshed = json.loads(special_file.read_text())
            rows = {row["id"]: row for bucket in refreshed["treatments"].values() for row in bucket}
            for identity in ("styled-1", "degrade-1", "smooth-1"):
                self.assertEqual(rows[identity]["status"], "processed")
                self.assertEqual(rows[identity]["result"], {
                    "run_id": "run-" + identity, "output": "kept.png"})
            self.assertEqual(rows["styled-2"]["status"], "pending")
            self.assertEqual(refreshed["reexecution_history"], [{"id": "history-1"}])

    def test_special_manifest_failure_is_reported_after_check_was_saved(self):
        with TemporaryDirectory() as temporary:
            root, manga, image, context = self._context(Path(temporary))
            with patch("central_v2.backend.routes.textoff_residue_occurrences.comparison_pairs",
                       return_value=[{"name": "page.png", "before": image, "after": image}]), \
                 patch("central_v2.backend.routes.auto_cleaner_check_special_treatments.rebuild_special_treatments",
                       side_effect=OSError("disk unavailable")):
                opened = json.loads(dispatch_get("/api/textoff/residue-occurrences?" +
                    urlencode(context), root).body)
                response = self._save_styled(root, context, opened, [self._decision("styled-1")])
            result = json.loads(response.body)
            self.assertEqual(response.status, 500)
            self.assertTrue(result["decision_persisted"])
            self.assertFalse(result["special_treatments_updated"])
            self.assertIn("disk unavailable", result["manifest_error"])
            self.assertTrue(check_path(manga, "1").is_file())

    def _context(self, root):
        manga = root / "comix" / "Candy YumYum (Yaoi)"
        (manga / "IMG" / "1").mkdir(parents=True)
        image = root / "page.png"
        Image.new("RGB", (80, 60), "white").save(image)
        return root, manga, image, {"provider": "comix", "manga": manga.name,
            "chapter": "1", "page": "page.png", "step": "1", "scope": "check"}

    def _decision(self, identity, left=.25, kind="balao_estilizado"):
        return {"id": identity, "type": kind, "box_normalized": {
            "left": left, "top": .2, "width": .2, "height": .2}}

    def _save_styled(self, root, context, opened, rows):
        payload = {**context, "source_snapshot": opened["source_snapshot"],
            "pages": [{"page": "page.png", "occurrences": [
                {**row, "number": index + 1} for index, row in enumerate(rows)]}]}
        return dispatch_post("/api/textoff/residue-occurrences", payload, root)
