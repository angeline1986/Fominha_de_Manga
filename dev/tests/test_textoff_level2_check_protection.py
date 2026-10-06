"""Approved Check decisions are the Level II protection authority."""
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from central_v2.backend.orchestration.textoff_merged.level2_manual_protection import (
    load_level1_protection, protect_level2_masks,
)


class CheckProtectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.manga = Path(self.temp.name) / "comix" / "Gazing at you"
        self.root = self.manga / "FLUXO_SECUNDARIO/04_TEXTO_OFF"
        self.check = self.root / "04_AUTO_CLEANER_CHECK/1/auto-cleaner-check-manifest.json"
        self.catalog = self.root / "RESIDUE_OCCURRENCES/1/residue-occurrences-manifest.json"

    @staticmethod
    def row(kind, origin="MANUAL", key="item", page="page.png"):
        return {"id": key, "page": page, "tipo": kind, "origin": origin,
                "origins": [origin], "box_normalized": {
                    "left": .25, "top": .25, "width": .5, "height": .5}}

    def write_check(self, rows):
        self.check.parent.mkdir(parents=True, exist_ok=True)
        self.check.write_text(json.dumps({
            "schema": "textoff_auto_cleaner_check_manifest_v1", "version": 1,
            "provider": "comix", "manga": "Gazing at you", "chapter": "1",
            "source_snapshot": {}, "approved_occurrences": rows,
        }), encoding="utf-8")

    def write_catalog(self, rows):
        self.catalog.parent.mkdir(parents=True, exist_ok=True)
        self.catalog.write_text(json.dumps({
            "schema": "textoff_residue_occurrence_manifest_v1",
            "documento": {"provider": "comix", "obra": "Gazing at you", "capitulo": "1"},
            "pages": {"page.png": {"steps": {"1": {"ocorrencias": rows}}}},
        }), encoding="utf-8")

    def load(self):
        return load_level1_protection(self.manga, "comix", "Gazing at you", "1")

    def test_check_protects_both_types_from_sommelier_and_manual(self):
        rows = [self.row(kind, origin, f"{origin}-{kind}")
                for origin in ("SOMMELIER", "MANUAL")
                for kind in ("residuo_degrade", "residuo_gradiente")]
        self.write_check(rows)
        loaded = self.load()["page.png"]
        self.assertEqual([row["id"] for row in loaded], [row["id"] for row in rows])
        self.assertEqual([row["origin"] for row in loaded], [row["origin"] for row in rows])

    def test_origin_does_not_control_protection_and_other_types_are_ignored(self):
        self.write_check([self.row("residuo_gradiente", "MAPEAR"),
                          self.row("texto_residual", "MAPEAR", "other")])
        self.assertEqual([row["tipo"] for row in self.load()["page.png"]],
                         ["residuo_gradiente"])

    def test_removed_check_occurrence_is_not_rebuilt_from_catalog(self):
        rejected = self.row("residuo_degrade", "SOMMELIER", "rejected")
        self.write_catalog([rejected])
        for relative in ("BUBBLE_SOMMELIER/1/report.json",
                         "TO_MERGED_NIVEL_III/1/json/styled-balloon-report.json"):
            source = self.root / relative
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text(json.dumps({"occurrence_id": "rejected"}), encoding="utf-8")
        self.write_check([])
        self.assertEqual(self.load(), {})

    def test_missing_check_preserves_legacy_catalog(self):
        legacy = self.row("residuo_gradiente", key="legacy")
        self.write_catalog([legacy])
        self.assertEqual(self.load(), {"page.png": [legacy]})

    def test_check_without_catalog_still_protects(self):
        approved = self.row("residuo_degrade")
        self.write_check([approved])
        self.assertFalse(self.catalog.exists())
        self.assertEqual(self.load(), {"page.png": [approved]})

    def test_check_and_catalog_do_not_duplicate_or_resurrect(self):
        shared = self.row("residuo_degrade", key="shared")
        removed = self.row("residuo_gradiente", key="removed")
        self.write_catalog([shared, removed])
        self.write_check([shared])
        self.assertEqual(self.load(), {"page.png": [shared]})

    def test_loaded_check_box_subtracts_automatic_mask(self):
        self.write_check([self.row("residuo_gradiente", "MANUAL")])
        automatic = np.full((20, 20), 255, dtype=np.uint8)
        masks, summary = protect_level2_masks(
            [automatic], self.load()["page.png"], automatic.shape)
        self.assertEqual(summary["protected_occurrences"], 1)
        self.assertGreater(summary["protected_pixels"], 0)
        self.assertLess(summary["mask_pixels_after_protection"],
                        summary["mask_pixels_before_protection"])
        self.assertEqual(int(np.count_nonzero(masks[0][5:15, 5:15])), 0)

    def test_invalid_check_is_not_silently_replaced_by_catalog(self):
        self.write_catalog([self.row("residuo_degrade")])
        self.write_check([self.row("residuo_gradiente")])
        payload = json.loads(self.check.read_text())
        payload["provider"] = "another"
        self.check.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "estrutura incompatível"):
            self.load()


if __name__ == "__main__":
    unittest.main()
