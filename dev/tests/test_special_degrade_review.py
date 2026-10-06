"""Persisted Degradê review serves only verified historical images."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from urllib.parse import urlencode

from central_v2.backend.orchestration.textoff_special.artifacts import sha256
from central_v2.backend.orchestration.textoff_merged.special_degrade_review import review_pairs
from central_v2.backend.orchestration.textoff_merged.special_degrade_output import SCHEMA
from central_v2.backend.orchestration.textoff_merged.special_treatments_manifest import (
    SCHEMA as SPECIAL_SCHEMA, manifest_path as special_path,
)
from central_v2.backend.orchestration.textoff_merged.special_treatments_query import query_special_treatments
from central_v2.backend.orchestration.textoff_merged.stages import LEVEL1, LEVEL2, stage_chapter
from central_v2.backend.routes.router import dispatch_get


class DegradeReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manga = self.root / "comix" / "Example"
        (self.manga / "IMG/1").mkdir(parents=True)
        self.stage = stage_chapter(self.manga, "PINCEL_DEGRADE", "1", read_legacy=False)
        (self.stage / "json").mkdir(parents=True)
        (self.stage / "clean").mkdir()
        self.manifest = self.stage / "json/degrade-manifest.json"
        self.rois = [{"x": 113, "y": 3378, "width": 447, "height": 355},
                     {"x": 453, "y": 3763, "width": 355, "height": 283}]
        self.write_record()

    def write_record(self, level=LEVEL2, status="processed"):
        before = stage_chapter(self.manga, level, "1") / "clean/page_clean.png"
        before.parent.mkdir(parents=True, exist_ok=True)
        before.write_bytes(b"historical input " + level.encode())
        after = self.stage / "clean/page_degrade.png"
        after.write_bytes(b"degrade output")
        row = {"provider": "comix", "manga": "Example", "chapter": "1", "page": "page.png",
               "treatment": "degrade", "status": status, "selected_from": level,
               "input": {"path": str(before), "sha256": sha256(before)},
               "output": {"artifact": "clean/page_degrade.png", "sha256": sha256(after)},
               "occurrence_ids": ["approved-1", "approved-2"], "rois": self.rois,
               "run_id": "run123"}
        self.manifest.write_text(json.dumps({"schema": SCHEMA, "version": 1,
            "provider": "comix", "manga": "Example", "chapter": "1",
            "treatment": "degrade", "pages": {"page.png": row}}), encoding="utf-8")
        return before, after

    def request(self, *, side=None, page="0", version=""):
        query = {"provider": "comix", "manga": "Example", "chapter": "1",
                 "step": "degrade", "comparisonMode": "degrade", "scope": "degrade"}
        if side:
            query.update(side=side, page=page, version=version)
        url = "/api/textoff/comparison" + ("/image" if side else "") + "?" + urlencode(query)
        return dispatch_get(url, self.root)

    def test_exact_persisted_pair_and_two_rois_served(self):
        before, after = self.write_record(LEVEL1)
        result = self.request()
        self.assertEqual(result.status, 200)
        pages = json.loads(result.body)["pages"]
        self.assertEqual([page["name"] for page in pages], ["page.png"])
        self.assertEqual(pages[0]["rois"], self.rois)
        self.assertEqual(pages[0]["occurrence_ids"], ["approved-1", "approved-2"])
        self.assertEqual(pages[0]["selected_from"], LEVEL1)
        self.assertEqual(pages[0]["input_sha256"], sha256(before))
        self.assertEqual(pages[0]["output_sha256"], sha256(after))
        version = pages[0]["version"]
        self.assertEqual(self.request(side="before", version=version).body, before.read_bytes())
        self.assertEqual(self.request(side="after", version=version).body, after.read_bytes())
        self.assertEqual(self.request(side="after", version="wrong").status, 404)
        self.assertEqual(len(review_pairs(self.manga, "comix", "1")), 1)

    def test_no_change_valid_and_other_pages_not_listed(self):
        self.write_record(status="no_change")
        manifest = json.loads(self.manifest.read_text(encoding="utf-8"))
        manifest["pages"]["unprocessed.png"] = {"page": "unprocessed.png", "chapter": "1",
            "provider": "comix", "manga": "Example", "treatment": "degrade", "status": "failed"}
        self.manifest.write_text(json.dumps(manifest), encoding="utf-8")
        self.assertEqual([page["name"] for page in json.loads(self.request().body)["pages"]], ["page.png"])

    def test_missing_or_changed_artifacts_disable_review(self):
        special = special_path(self.manga, "1")
        special.parent.mkdir(parents=True)
        special.write_text(json.dumps({"schema": SPECIAL_SCHEMA, "version": 1,
            "provider": "comix", "manga": "Example", "chapter": "1",
            "treatments": {"degrade": [{"treatment": "degrade", "status": "processed",
            "page": "page.png"}]} }), encoding="utf-8")
        summary = query_special_treatments(self.manga, "comix", "degrade")
        self.assertTrue(summary["chapters"][0]["review_available"])
        before = Path(json.loads(self.manifest.read_text())["pages"]["page.png"]["input"]["path"])
        before.write_bytes(b"changed")
        self.assertEqual(self.request().status, 404)
        self.assertFalse(query_special_treatments(self.manga, "comix", "degrade")["chapters"][0]["review_available"])
        self.write_record()
        (self.stage / "clean/page_degrade.png").unlink()
        self.assertEqual(self.request().status, 404)


if __name__ == "__main__":
    unittest.main()
