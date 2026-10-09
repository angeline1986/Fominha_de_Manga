"""Derived special-treatment bootstrap never promotes raw source suggestions."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from central_v2.backend.orchestration.textoff_merged.auto_cleaner_check_manifest import (
    SCHEMA as CHECK_SCHEMA, manifest_path as check_path,
)
from central_v2.backend.orchestration.textoff_merged.special_treatments_bootstrap import bootstrap
from central_v2.backend.orchestration.textoff_merged.special_treatments_manifest import (
    STATUSES, rebuild_special_treatments,
)
from central_v2.backend.orchestration.textoff_special.artifacts import sha256


class SpecialTreatmentsManifestTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manga = self.root / "comix" / "Example"
        self.document = {"provider": "comix", "obra": "Example", "capitulo": "1"}
        self.source = check_path(self.manga, "1")
        self.source.parent.mkdir(parents=True)

    def row(self, identity, kind, *, page="page.png"):
        return {
            "id": identity, "page": page, "tipo": kind,
            "box_normalized": {"left": .1, "top": .2, "width": .3, "height": .4},
            "box_pixels": {"x": 10, "y": 20, "width": 30, "height": 40},
            "origin": "MAPEAR", "origins": ["MAPEAR", "SOMMELIER"],
            "source_classification": "soft_gradient",
            "source_references": [{"origin": "MAPEAR", "detection": 2}],
        }

    def write_check(self, rows):
        payload = {
            "schema": CHECK_SCHEMA, "version": 1, "provider": "comix",
            "manga": "Example", "chapter": "1", "updated_at": "fixed",
            "source_snapshot": {}, "approved_occurrences": rows,
        }
        self.source.write_text(json.dumps(payload), encoding="utf-8")

    def test_approved_degrade_and_smooth_gradient_preserve_metadata(self):
        degrade = self.row("approved", "residuo_degrade")
        gradient = self.row("manual", "residuo_gradiente")
        self.write_check([degrade, gradient, self.row("other", "texto_residual")])
        source_hash = sha256(self.source)
        target, payload, written = rebuild_special_treatments(self.manga, self.document, "1")
        self.assertTrue(written)
        self.assertEqual(sha256(self.source), source_hash)
        self.assertEqual(payload["source_check"]["sha256"], source_hash)
        self.assertEqual(payload["treatments"]["degrade"][0]["id"], "approved")
        self.assertEqual(payload["treatments"]["degrade"][0]["box_pixels"], degrade["box_pixels"])
        self.assertEqual(payload["treatments"]["degrade"][0]["box_normalized"], degrade["box_normalized"])
        self.assertEqual(payload["treatments"]["degrade"][0]["origins"], degrade["origins"])
        self.assertEqual(payload["treatments"]["degrade"][0]["source_references"], degrade["source_references"])
        self.assertEqual(payload["treatments"]["degrade"][0]["status"], "pending")
        smooth = payload["treatments"]["gradiente_suave"][0]
        self.assertEqual(smooth["id"], "manual")
        self.assertEqual(smooth["tipo"], "residuo_gradiente")
        self.assertEqual(smooth["box_pixels"], gradient["box_pixels"])
        self.assertEqual(smooth["source_classification"], gradient["source_classification"])
        self.assertEqual(smooth["source_references"], gradient["source_references"])
        self.assertEqual(payload["unclassified"], [])
        self.assertEqual(payload["treatments"]["estilizado"], [])
        self.assertNotIn("other", target.read_text(encoding="utf-8"))
        self.assertEqual(STATUSES, {"pending", "processed", "no_change", "failed"})

    def test_styled_balloon_routes_only_to_existing_artistic_bucket(self):
        styled = self.row("art", "balao_estilizado")
        self.write_check([styled, self.row("deg", "residuo_degrade"),
                          self.row("soft", "residuo_gradiente"),
                          self.row("ignore", "texto_residual")])
        _, payload, _ = rebuild_special_treatments(self.manga, self.document, "1")
        artistic = payload["treatments"]["estilizado"][0]
        self.assertEqual((artistic["id"], artistic["page"], artistic["tipo"]),
                         ("art", "page.png", "balao_estilizado"))
        self.assertEqual(artistic["status"], "pending")
        self.assertEqual(artistic["box_pixels"], styled["box_pixels"])
        self.assertEqual(artistic["source_references"], styled["source_references"])
        self.assertEqual([row["id"] for row in payload["treatments"]["degrade"]], ["deg"])
        self.assertEqual([row["id"] for row in payload["treatments"]["gradiente_suave"]], ["soft"])
        self.assertEqual(payload["unclassified"], [])
        self.assertNotIn("ignore", json.dumps(payload["treatments"]))

    def test_repeat_is_idempotent_and_preserves_processing_state(self):
        self.write_check([self.row("one", "residuo_degrade"),
                          self.row("one", "residuo_degrade")])
        target, payload, _ = rebuild_special_treatments(self.manga, self.document, "1")
        self.assertEqual(len(payload["treatments"]["degrade"]), 1)
        payload["treatments"]["degrade"][0]["status"] = "processed"
        target.write_text(json.dumps(payload), encoding="utf-8")
        before = target.read_bytes()
        _, repeated, written = rebuild_special_treatments(self.manga, self.document, "1")
        self.assertFalse(written)
        self.assertEqual(target.read_bytes(), before)
        self.assertEqual(repeated["treatments"]["degrade"][0]["status"], "processed")

    def test_check_removal_rebuilds_without_resurrecting_raw_items(self):
        self.write_check([self.row("removed", "residuo_degrade"),
                          self.row("kept", "residuo_degrade")])
        target, _, _ = rebuild_special_treatments(self.manga, self.document, "1")
        self.write_check([self.row("kept", "residuo_degrade")])
        _, payload, written = rebuild_special_treatments(self.manga, self.document, "1")
        self.assertTrue(written)
        self.assertEqual([item["id"] for item in payload["treatments"]["degrade"]], ["kept"])
        self.assertNotIn("removed", target.read_text(encoding="utf-8"))

    def test_changed_routing_rebuilds_with_unchanged_check_hash(self):
        self.write_check([self.row("smooth", "residuo_gradiente")])
        target, payload, _ = rebuild_special_treatments(self.manga, self.document, "1")
        old = payload["treatments"]["gradiente_suave"].pop()
        old["treatment"] = None
        old["classification_block"] = "gradiente_sem_destino_inequivoco"
        payload["unclassified"].append(old)
        target.write_text(json.dumps(payload), encoding="utf-8")
        source_hash = sha256(self.source)
        _, refreshed, written = rebuild_special_treatments(self.manga, self.document, "1")
        self.assertTrue(written)
        self.assertEqual(refreshed["source_check"]["sha256"], source_hash)
        self.assertEqual(sha256(self.source), source_hash)
        self.assertEqual(len(refreshed["treatments"]["gradiente_suave"]), 1)
        self.assertEqual(refreshed["unclassified"], [])

    def test_bootstrap_reads_only_persisted_check(self):
        self.write_check([self.row("approved", "residuo_degrade")])
        source_hash = sha256(self.source)
        first = bootstrap(self.root)
        second = bootstrap(self.root)
        self.assertEqual(len(first), 1)
        self.assertTrue(first[0]["written"])
        self.assertFalse(second[0]["written"])
        self.assertEqual(first[0]["degrade"], 1)
        self.assertEqual(sha256(self.source), source_hash)


if __name__ == "__main__":
    unittest.main()
