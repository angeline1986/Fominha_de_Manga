"""Read-only special-treatment worklist endpoint tests."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from urllib.parse import urlencode

from central_v2.backend.routes.router import dispatch_get
from central_v2.backend.orchestration.textoff_merged.special_treatments_manifest import (
    SCHEMA, manifest_path,
)
from central_v2.backend.orchestration.textoff_special.artifacts import sha256


class SpecialTreatmentsRouteTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name)
        self.manga = self.output / "comix" / "Example"
        (self.manga / "IMG" / "1").mkdir(parents=True)
        self.source = manifest_path(self.manga, "1")
        self.source.parent.mkdir(parents=True)

    def row(self, identity, page, treatment, status="pending"):
        return {"id": identity, "page": page, "treatment": treatment, "status": status}

    def write_manifest(self, buckets):
        self.source.write_text(json.dumps({
            "schema": SCHEMA, "version": 1, "provider": "comix", "manga": "Example",
            "chapter": "1", "source_check": {"sha256": "persisted"},
            "treatments": buckets, "unclassified": [],
        }), encoding="utf-8")

    def get(self, treatment):
        query = urlencode({"provider": "comix", "manga": "Example", "treatment": treatment})
        response = dispatch_get(f"/api/textoff/special/treatments?{query}", self.output)
        return response.status, json.loads(response.body)

    def test_filters_and_groups_without_touching_manifest(self):
        self.write_manifest({
            "degrade": [self.row("a", "page-a.png", "degrade"),
                        self.row("b", "page-a.png", "degrade")],
            "estilizado": [],
            "gradiente_suave": [self.row("c", "page-b.png", "gradiente_suave", "processed"),
                               self.row("d", "page-b.png", "gradiente_suave", "no_change"),
                               self.row("e", "page-c.png", "gradiente_suave", "processed")],
        })
        before = sha256(self.source)
        status, degrade = self.get("degrade")
        self.assertEqual(status, 200)
        self.assertEqual(degrade["summary"], {"chapters": 1, "pages": 1, "occurrences": 2})
        self.assertEqual(degrade["chapters"][0]["pages"], ["page-a.png"])
        self.assertEqual(degrade["chapters"][0]["status"], "pending")
        _, suave = self.get("gradiente_suave")
        self.assertEqual(suave["summary"], {"chapters": 1, "pages": 2, "occurrences": 3})
        self.assertEqual(suave["chapters"][0]["statuses"], ["no_change", "processed"])
        _, artistic = self.get("estilizado")
        self.assertEqual(artistic, {"treatment": "estilizado", "chapters": [],
                                    "summary": {"chapters": 0, "pages": 0, "occurrences": 0}})
        self.assertEqual(sha256(self.source), before)

    def test_invalid_treatment_is_rejected(self):
        self.write_manifest({"degrade": [], "estilizado": [], "gradiente_suave": []})
        status, payload = self.get("../../IMG")
        self.assertEqual(status, 400)
        self.assertIn("Tratamento especial inválido", payload["error"])

    def test_missing_manifest_has_valid_empty_collection(self):
        status, payload = self.get("estilizado")
        self.assertEqual(status, 200)
        self.assertEqual(payload["summary"]["occurrences"], 0)
        self.assertEqual(payload["chapters"], [])


if __name__ == "__main__":
    unittest.main()
