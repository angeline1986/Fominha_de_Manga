"""Synthetic tests for historical Suave comparison pairs."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from urllib.parse import urlencode

from central_v2.backend.orchestration.textoff_special.artifacts import sha256
from central_v2.backend.orchestration.textoff_special.catalog import treatment_for
from central_v2.backend.orchestration.textoff_merged.artifact_paths import artifact_ref
from central_v2.backend.orchestration.textoff_merged.special_smooth_output import SCHEMA
from central_v2.backend.orchestration.textoff_merged.special_smooth_review import review_pairs
from central_v2.backend.orchestration.textoff_merged.special_treatments_manifest import manifest_path
from central_v2.backend.orchestration.textoff_merged.special_treatments_query import query_special_treatments
from central_v2.backend.orchestration.textoff_merged.stages import LEVEL1, stage_chapter
from central_v2.backend.routes.router import dispatch_get


class SmoothReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manga = self.root / "comix" / "Example"
        (self.manga / "IMG/1").mkdir(parents=True)
        self.output_stage = stage_chapter(self.manga, "PINCEL_SUAVE", "1", read_legacy=False)
        self.consolidated = stage_chapter(self.manga, "TO_MERGED_CONSOLIDADO", "1", read_legacy=False)
        self.source_stage = stage_chapter(self.manga, LEVEL1, "1", read_legacy=False)
        self.records, selections, approved = {}, [], []
        for index in range(5):
            page = f"page-{index:03}.png"
            source_ref = artifact_ref("clean", f"page-{index:03}_clean.png")
            output_ref = artifact_ref("clean", f"page-{index:03}_suave.png")
            source, output = self.source_stage / source_ref, self.output_stage / output_ref
            source.parent.mkdir(parents=True, exist_ok=True)
            output.parent.mkdir(parents=True, exist_ok=True)
            source.write_bytes(f"historical input {index}".encode())
            output.write_bytes(f"smooth output {index}".encode())
            selections.append({"source": page, "artifact": source_ref,
                               "selected_from": LEVEL1, "sha256": sha256(source)})
            self.records[page] = self.record(page, source, output)
            approved.append({"id": f"roi-{index}", "page": page,
                             "treatment": "gradiente_suave", "status": "processed"})
        self.consolidated_manifest = self.consolidated / "json/clean-manifest.json"
        self.consolidated_manifest.parent.mkdir(parents=True, exist_ok=True)
        self.consolidated_manifest.write_text(json.dumps({"selections": selections}), encoding="utf-8")
        for row in self.records.values():
            row["consolidated_manifest"]["sha256"] = sha256(self.consolidated_manifest)
        self.manifest = self.output_stage / "json/suave-manifest.json"
        self.manifest.parent.mkdir(parents=True, exist_ok=True)
        self.write_manifest()
        special = manifest_path(self.manga, "1")
        special.parent.mkdir(parents=True, exist_ok=True)
        special.write_text(json.dumps({"schema": "textoff_special_treatments_manifest_v1",
            "version": 1, "provider": "comix", "manga": "Example", "chapter": "1",
            "treatments": {"gradiente_suave": approved}}), encoding="utf-8")

    def record(self, page, source, output, status="processed"):
        return {"provider": "comix", "manga": "Example", "chapter": "1", "page": page,
            "treatment": "gradiente_suave", "status": status, "selected_from": LEVEL1,
            "occurrence_ids": [f"roi-{page}"], "rois": [{"x": 1, "y": 2, "width": 3, "height": 4}],
            "input": {"path": str(source), "sha256": sha256(source)},
            "consolidated_manifest": {"path": str(self.consolidated / "json/clean-manifest.json"),
                                      "sha256": "pending"},
            "output": {"artifact": f"clean/{Path(page).stem}_suave.png", "sha256": sha256(output)},
            "run_id": f"run{Path(page).stem[-3:]}"}

    def write_manifest(self):
        self.manifest.write_text(json.dumps({"schema": SCHEMA, "version": 1,
            "provider": "comix", "manga": "Example", "chapter": "1",
            "treatment": "gradiente_suave",
            "algorithm": treatment_for("gradiente_suave").algorithm, "pages": self.records}),
            encoding="utf-8")

    def request(self, *, side=None, page="0", version=""):
        query = {"provider": "comix", "manga": "Example", "chapter": "1",
                 "step": "suave", "comparisonMode": "suave", "scope": "suave"}
        if side:
            query.update(side=side, page=page, version=version)
        path = "/api/textoff/comparison" + ("/image" if side else "") + "?" + urlencode(query)
        return dispatch_get(path, self.root)

    def test_five_historical_pairs_and_images_are_served(self):
        response = self.request()
        self.assertEqual(response.status, 200)
        pages = json.loads(response.body)["pages"]
        self.assertEqual([row["name"] for row in pages], [f"page-{i:03}.png" for i in range(5)])
        selected = pages[3]
        pair = review_pairs(self.manga, "comix", "1")[3]
        self.assertEqual(self.request(side="before", page=selected["id"], version=selected["version"]).body,
                         pair["before"].read_bytes())
        self.assertEqual(self.request(side="after", page=selected["id"], version=selected["version"]).body,
                         pair["after"].read_bytes())
        self.assertTrue(query_special_treatments(self.manga, "comix", "gradiente_suave")
                        ["chapters"][0]["review_available"])

    def test_pending_failed_and_hash_mismatches_disable_review(self):
        for status in ("pending", "failed"):
            for row in self.records.values():
                row["status"] = status
            self.write_manifest()
            self.assertFalse(query_special_treatments(self.manga, "comix", "gradiente_suave")
                             ["chapters"][0]["review_available"])
        for row in self.records.values():
            row["status"] = "processed"
        self.write_manifest()
        page = "page-000.png"
        output = self.output_stage / self.records[page]["output"]["artifact"]
        listed = json.loads(self.request().body)["pages"][0]
        output.write_bytes(b"changed output")
        self.assertEqual(self.request(side="after", version=listed["version"]).status, 404)
        self.assertFalse(query_special_treatments(self.manga, "comix", "gradiente_suave")
                         ["chapters"][0]["review_available"])
        output.write_bytes(b"smooth output 0")
        listed = json.loads(self.request().body)["pages"][0]
        source = Path(self.records[page]["input"]["path"])
        source.write_bytes(b"changed input")
        self.assertEqual(self.request(side="before", version=listed["version"]).status, 404)


if __name__ == "__main__":
    unittest.main()
