"""Auto-Cleaner Check consolidates persisted suggestions without rerunning sources."""
import json
from pathlib import Path
import tempfile
import unittest
from urllib.parse import urlencode
from unittest.mock import patch

from PIL import Image

from central_v2.backend.routes.router import dispatch_get, dispatch_post
from central_v2.backend.orchestration.textoff_merged import (
    auto_cleaner_check, auto_cleaner_check_extractors,
)


class AutoCleanerCheckTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.manga = self.root / "ridi" / "obra"
        self.manga.mkdir(parents=True)
        self.after = self.root / "after.png"
        Image.new("RGB", (64, 32), "white").save(self.after)
        self.pairs = [{"name": "page-A.png", "before": self.after, "after": self.after},
                      {"name": "page-B.png", "before": self.after, "after": self.after}]
        self.pairs_patch = patch(
            "central_v2.backend.routes.textoff_residue_occurrences.comparison_pairs",
            return_value=self.pairs,
        )
        self.pairs_patch.start()
        self.addCleanup(self.pairs_patch.stop)
        self.consolidated_patch = patch.object(
            auto_cleaner_check_extractors,
            "consolidated_image", return_value=self.after,
        )
        self.consolidated_patch.start()
        self.addCleanup(self.consolidated_patch.stop)
        self.mapear_path = (self.manga / "FLUXO_SECUNDARIO/04_TEXTO_OFF/"
                            "TO_MERGED_NIVEL_III/12/json/styled-balloon-report.json")
        self.sommelier_path = (self.manga / "FLUXO_SECUNDARIO/04_TEXTO_OFF/"
                               "BUBBLE_SOMMELIER/12/report.json")

    def context(self, page="page-A.png"):
        return {"provider": "ridi", "manga": "obra", "chapter": "12",
                "page": page, "step": "1", "scope": "check"}

    def check_get(self, page="page-A.png"):
        response = dispatch_get("/api/textoff/residue-occurrences?" +
                                urlencode(self.context(page)), self.root)
        return response, json.loads(response.body)

    def check_post(self, data, occurrences, page="page-A.png"):
        submitted = [{
            **row, "number": row.get("numero", index + 1),
            "type": row.get("tipo", ""), "note": row.get("observacao"),
        } for index, row in enumerate(occurrences)]
        payload = {**self.context(page), "source_snapshot": data["source_snapshot"],
                   "pages": [{"page": page, "occurrences": submitted}]}
        response = dispatch_post("/api/textoff/residue-occurrences", payload, self.root)
        return response, json.loads(response.body)

    def write_sources(self):
        self.mapear_path.parent.mkdir(parents=True)
        self.mapear_path.write_text(json.dumps({"pages": [{
            "source": "page-A_clean.png",
            "styled_balloon_candidates": [
                {"bbox": [16, 8, 16, 8], "candidate_type": "soft_gradient", "detection": 4},
                {"bbox": [40, 8, 12, 8], "candidate_type": "irregular_outline", "detection": 5},
            ],
        }]}), encoding="utf-8")
        self.sommelier_path.parent.mkdir(parents=True)
        self.sommelier_path.write_text(json.dumps({"pages": [{
            "page_id": "page-A.png", "width": 64, "height": 32,
            "bubbles": [
                {"identity": "page-A-bubble-01", "bubble_index": 1, "candidate": True,
                 "label": "speech_balloon", "bbox": {"x1": 16, "y1": 8, "x2": 32, "y2": 16}},
                {"identity": "page-A-bubble-02", "bubble_index": 2, "candidate": True,
                 "label": "speech_balloon", "bbox": {"x1": 2, "y1": 2, "x2": 10, "y2": 10}},
                {"identity": "page-A-bubble-negative", "candidate": False,
                 "bbox": {"x1": 45, "y1": 20, "x2": 55, "y2": 28}},
            ],
        }]}), encoding="utf-8")

    def add_manual_catalog_item(self):
        response = dispatch_post("/api/textoff/residue-occurrences", {
            "provider": "ridi", "manga": "obra", "chapter": "12", "step": "1",
            "page": "page-A.png", "occurrences": [{
                "id": "manual-old", "number": 1, "type": "outro", "note": "marca",
                "box_normalized": {"left": .75, "top": .1, "width": .1, "height": .2},
            }],
        }, self.root)
        self.assertEqual(response.status, 200)

    def test_first_open_reads_sources_and_deduplicates_exact_page_geometry(self):
        self.write_sources()
        mapear_before = self.mapear_path.read_bytes()
        sommelier_before = self.sommelier_path.read_bytes()
        with patch("central_v2.backend.orchestration.textoff_merged.level3_styled.execute_level3",
                   side_effect=AssertionError("Mapear must not rerun")), \
             patch("central_v2.backend.orchestration.bubble_sommelier.execution.execute",
                   side_effect=AssertionError("Sommelier must not rerun")):
            response, result = self.check_get()
        self.assertEqual(response.status, 200)
        self.assertFalse(result["decision_persisted"])
        self.assertEqual(len(result["occurrences"]), 3)
        overlapping = next(row for row in result["occurrences"]
                           if row["box_normalized"] == {
                               "left": .25, "top": .25, "width": .25, "height": .25})
        self.assertEqual(overlapping["origins"], ["MAPEAR", "SOMMELIER"])
        self.assertEqual(len(overlapping["source_references"]), 2)
        self.assertEqual(overlapping["tipo"], "residuo_gradiente")
        self.assertEqual(self.mapear_path.read_bytes(), mapear_before)
        self.assertEqual(self.sommelier_path.read_bytes(), sommelier_before)

    def test_legacy_manual_rows_without_origin_are_interpreted_as_manual(self):
        self.add_manual_catalog_item()
        old_manifest = (self.manga / "FLUXO_SECUNDARIO/04_TEXTO_OFF/"
                        "RESIDUE_OCCURRENCES/12/residue-occurrences-manifest.json")
        saved = json.loads(old_manifest.read_text(encoding="utf-8"))
        legacy_row = saved["pages"]["page-A.png"]["steps"]["1"]["ocorrencias"][0]
        legacy_row.pop("origin", None)
        legacy_row.pop("origins", None)
        old_manifest.write_text(json.dumps(saved), encoding="utf-8")
        response, result = self.check_get()
        self.assertEqual(response.status, 200)
        manual = next(row for row in result["occurrences"] if row["id"] == "manual-old")
        self.assertEqual(manual["origin"], "MANUAL")
        saved = json.loads(old_manifest.read_text(encoding="utf-8"))
        self.assertNotIn("origin", saved["pages"]["page-A.png"]["steps"]["1"]["ocorrencias"][0])

    def test_round_trip_preserves_all_origins_and_rejected_rows_do_not_return(self):
        self.write_sources()
        self.add_manual_catalog_item()
        _, initial = self.check_get()
        rows = initial["occurrences"]
        self.assertEqual({row["origin"] for row in rows}, {"MAPEAR", "SOMMELIER", "MANUAL"})
        removed = next(row for row in rows if row["origin"] == "MAPEAR"
                       and row["box_normalized"]["left"] > .5)
        kept = [row for row in rows if row["id"] != removed["id"]]
        source_reports = (self.mapear_path.read_bytes(), self.sommelier_path.read_bytes())
        response, saved = self.check_post(initial, kept)
        self.assertEqual(response.status, 200, saved)
        _, reopened = self.check_get()
        self.assertTrue(reopened["decision_persisted"])
        self.assertNotIn(removed["id"], [row["id"] for row in reopened["occurrences"]])
        self.assertEqual({row["origin"] for row in reopened["occurrences"]},
                         {"MAPEAR", "SOMMELIER", "MANUAL"})
        self.assertEqual((self.mapear_path.read_bytes(), self.sommelier_path.read_bytes()), source_reports)
        check_manifest = (self.manga / "FLUXO_SECUNDARIO/04_TEXTO_OFF/"
                          "04_AUTO_CLEANER_CHECK/12/auto-cleaner-check-manifest.json")
        self.assertTrue(check_manifest.is_file())
        payload = json.loads(check_manifest.read_text(encoding="utf-8"))
        self.assertEqual(payload["schema"], "textoff_auto_cleaner_check_manifest_v1")
        self.assertEqual(payload["provider"], "ridi")
        self.assertEqual(payload["manga"], "obra")
        self.assertEqual(payload["chapter"], "12")
        self.assertEqual(payload["approved_occurrences"], reopened["occurrences"])

    def test_sources_changed_after_saved_decision_are_flagged_without_repopulation(self):
        self.write_sources()
        _, initial = self.check_get()
        rows = initial["occurrences"]
        response, _ = self.check_post(initial, rows)
        self.assertEqual(response.status, 200)
        original_ids = [row["id"] for row in rows]
        report = json.loads(self.mapear_path.read_text(encoding="utf-8"))
        report["pages"][0]["styled_balloon_candidates"].append({
            "bbox": [2, 20, 8, 8], "candidate_type": "new_kind", "detection": 9,
        })
        self.mapear_path.write_text(json.dumps(report), encoding="utf-8")
        _, reopened = self.check_get()
        self.assertEqual([row["id"] for row in reopened["occurrences"]], original_ids)
        self.assertEqual(reopened["stale_sources"], ["mapear"])

    def test_absent_sources_are_reported_and_check_is_a_new_stage_only(self):
        response, result = self.check_get()
        self.assertEqual(response.status, 200)
        self.assertEqual(result["occurrences"], [])
        self.assertFalse(result["decision_persisted"])
        self.assertEqual({value["status"] for value in result["source_status"].values()}, {"missing"})
        manifest = (self.manga / "FLUXO_SECUNDARIO/04_TEXTO_OFF/"
                    "04_AUTO_CLEANER_CHECK/12/auto-cleaner-check-manifest.json")
        self.assertFalse(manifest.exists())
        registry = json.loads(auto_cleaner_check.__file__ and
                              (Path(auto_cleaner_check.__file__).with_name("artifact-migration-registry.json")
                               .read_text(encoding="utf-8")))
        check = next(stage for stage in registry["stages"]
                     if stage["stage_id"] == "auto_cleaner_check")
        self.assertIsNone(check["legacy_path"])
        self.assertEqual(check["classification"], "NEW_STAGE")
        self.assertFalse(check["dual_write"])


if __name__ == "__main__":
    unittest.main()
