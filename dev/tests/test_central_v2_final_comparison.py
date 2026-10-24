"""The quality audit serves the verified final image when it exists."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import urlencode

from central_v2.backend.orchestration.textoff_merged import final_comparison
from central_v2.backend.orchestration.textoff_merged.final_consolidated import final_manifest_path
from central_v2.backend.routes.router import dispatch_get


class FinalComparisonTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manga = self.root / "ridi/obra"
        self.manga.mkdir(parents=True)
        (self.manga / "IMG/1").mkdir(parents=True)
        (self.manga / "IMG/1/page.png").write_bytes(b"catalog")
        images = {}
        for side in ("original", "level1", "level2"):
            image = self.manga / f"{side}.png"
            image.write_bytes(side.encode())
            images[side] = image
        self.page = {"name": "page.png", **images, "level2_status": "changed",
                     "level2_chapter_status": "processed"}
        self.stub = patch.object(final_comparison, "comparison_triplets", return_value=[self.page])
        self.stub.start()
        self.addCleanup(self.stub.stop)

    def request(self, **extra):
        query = dict(provider="ridi", manga="obra", chapter="1", step="1",
                     layout="quad", comparisonMode="before_after")
        query.update(extra)
        suffix = "/image" if "side" in extra else ""
        return dispatch_get("/api/textoff/comparison" + suffix + "?" + urlencode(query), self.root)

    def write_final(self, image=b"final"):
        manifest = final_manifest_path(self.manga, "1")
        manifest.parent.mkdir(parents=True, exist_ok=True)
        (manifest.parent.parent / "page.png").write_bytes(image)
        manifest.write_text(json.dumps({
            "schema": "textoff_consolidado_final_manifest_v1", "version": 1,
            "provider": "ridi", "manga": "obra", "chapter": "1",
            "pages": {"page.png": {"page": "page.png", "artifact": "page.png",
                                   "sha256": hashlib.sha256(image).hexdigest()}},
        }))

    def test_missing_final_keeps_earlier_stages_and_rejects_final_image(self):
        response = self.request()
        self.assertEqual(response.status, 200)
        page = json.loads(response.body)["pages"][0]
        self.assertFalse(page["final_available"])
        self.assertEqual(self.request(side="level2", page="0", version=page["version"]).body,
                         b"level2")
        self.assertEqual(self.request(side="final", page="0", version=page["version"]).status, 404)

    def test_final_image_is_served_and_version_changes_on_promotion(self):
        self.write_final()
        page = json.loads(self.request().body)["pages"][0]
        self.assertTrue(page["final_available"])
        response = self.request(side="final", page="0", version=page["version"])
        self.assertEqual(response.status, 200)
        self.assertEqual(response.body, b"final")
        self.write_final(b"promoted")
        self.assertEqual(self.request(side="final", page="0", version=page["version"]).status, 404)
        updated = json.loads(self.request().body)["pages"][0]
        self.assertNotEqual(updated["version"], page["version"])
        self.assertEqual(self.request(side="final", page="0", version=updated["version"]).body,
                         b"promoted")

    def test_corrupt_final_is_not_silently_shown(self):
        self.write_final()
        final = final_manifest_path(self.manga, "1").parent.parent / "page.png"
        final.write_bytes(b"tampered")
        self.assertEqual(self.request().status, 404)
