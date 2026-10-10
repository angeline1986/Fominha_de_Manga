"""Check images follow each Consolidado selection without changing other views."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from urllib.parse import urlencode

from central_v2.backend.orchestration.textoff_merged.consolidated import rebuild_consolidated
from central_v2.backend.orchestration.textoff_merged.level2_vision import ALGORITHM
from central_v2.backend.orchestration.textoff_merged.stages import LEVEL1, LEVEL2
from central_v2.backend.routes.router import dispatch_get


class CheckConsolidatedImageTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.manga = self.root / "ridi/obra"
        (self.manga / "IMG/1").mkdir(parents=True)
        self.names = ("page-a.png", "page-b.png")
        merge = self.manga / "FLUXO_SECUNDARIO/02_MERGE/1"
        merge.mkdir(parents=True)
        for name in self.names:
            (merge / name).write_bytes(b"original-" + name.encode())
        (merge / "merge-manifest.json").write_text(json.dumps({
            "merged_images": 2, "source_total_height": 20,
            "outputs": [{"file": name, "global_start": i * 10, "global_end": (i + 1) * 10}
                        for i, name in enumerate(self.names)],
        }))
        stages = self.manga / "FLUXO_SECUNDARIO/04_TEXTO_OFF"
        level1 = stages / LEVEL1 / "1"
        (level1 / "clean").mkdir(parents=True)
        (level1 / "json").mkdir()
        for name in self.names:
            (level1 / "clean" / name.replace(".png", "_clean.png")).write_bytes(
                b"level1-" + name.encode())
        level1_manifest = level1 / "json/clean-manifest.json"
        level1_manifest.write_text(json.dumps({
            "source_stage": "MERGE", "integrity_ok": True,
            "source_artifacts": list(self.names),
            "clean_artifacts": [f"clean/{name.replace('.png', '_clean.png')}" for name in self.names],
            "outputs_total": 2,
        }))
        level2 = stages / LEVEL2 / "1"
        for directory in ("clean", "mask", "json"):
            (level2 / directory).mkdir(parents=True)
        (level2 / "clean/page-b_clean.png").write_bytes(b"level2-page-b")
        (level2 / "mask/page-b_text_mask.png").write_bytes(b"mask")
        row = {"source": "page-b.png", "clean": "clean/page-b_clean.png",
               "level1_clean": "clean/page-b_clean.png", "mask": "mask/page-b_text_mask.png",
               "changed_pixels": 1, "mask_pixels": 1}
        (level2 / "json/level2-report.json").write_text(json.dumps({
            "integrity_ok": True, "pages_analyzed": 1,
            "pages": [{**row, "changed_outside_mask": 0}],
        }))
        (level2 / "json/clean-manifest.json").write_text(json.dumps({
            "algorithm": ALGORITHM, "source_stage": LEVEL1, "integrity_ok": True,
            "source_level1_manifest_sha256": hashlib.sha256(level1_manifest.read_bytes()).hexdigest(),
            "source_artifacts": list(self.names),
            "source_level1_artifacts": ["clean/page-b_clean.png"],
            "candidate_source_artifacts": ["page-b.png"],
            "analyzed_source_artifacts": ["page-b.png"],
            "changed_source_artifacts": ["page-b.png"], "unchanged_source_artifacts": [],
            "page_results": [row], "clean_artifacts": ["clean/page-b_clean.png"],
            "changed_artifacts": ["clean/page-b_clean.png"],
            "mask_artifacts": ["mask/page-b_text_mask.png"],
            "report": "json/level2-report.json", "pages_total": 1,
            "analyzed_pages_total": 1, "changed_pages_total": 1,
            "outputs_total": 1, "outcome": "visual_changes",
        }))
        rebuild_consolidated(self.manga, "1")
        # A physical L2 file alone must not override the Consolidado's L1 selection.
        (level2 / "clean/page-a_clean.png").write_bytes(b"unselected-level2-page-a")

    def request(self, endpoint, *, step="1", **options):
        query = {"provider": "ridi", "manga": "obra", "chapter": "1", "step": step, **options}
        return dispatch_get(endpoint + "?" + urlencode(query), self.root)

    def image(self, name, *, step="1", **options):
        endpoint = "/api/textoff/comparison"
        listing = self.request(endpoint, step=step, **options)
        self.assertEqual(listing.status, 200, listing.body)
        page = next(row for row in json.loads(listing.body)["pages"] if row["name"] == name)
        response = self.request(endpoint + "/image", step=step, side="after",
                                page=page["id"], version=page["version"], **options)
        self.assertEqual(response.status, 200, response.body)
        return response.body

    def test_check_uses_each_selection_and_keeps_original(self):
        options = {"comparisonMode": "check", "scope": "check"}
        self.assertEqual(self.image("page-a.png", **options), b"level1-page-a.png")
        self.assertEqual(self.image("page-b.png", **options), b"level1-page-b.png")
        listing = self.request("/api/textoff/comparison", **options)
        page = next(row for row in json.loads(listing.body)["pages"] if row["name"] == "page-b.png")
        original = self.request("/api/textoff/comparison/image", side="before",
                                page=page["id"], version=page["version"], **options)
        self.assertEqual(original.body, b"original-page-b.png")

    def test_regular_steps_and_scope_without_check_mode_are_unchanged(self):
        self.assertEqual(self.image("page-a.png"), b"level1-page-a.png")
        self.assertEqual(self.image("page-b.png"), b"level1-page-b.png")
        self.assertEqual(self.image("page-b.png", step="2"), b"level2-page-b")
        self.assertEqual(self.image("page-b.png", scope="check",
                                    comparisonMode="level1"), b"level1-page-b.png")

    def test_check_does_not_fall_back_when_consolidated_is_stale(self):
        manifest = (self.manga / "FLUXO_SECUNDARIO/04_TEXTO_OFF/"
                    "TO_MERGED_CONSOLIDADO/1/json/clean-manifest.json")
        payload = json.loads(manifest.read_text())
        payload["selections"][1]["sha256"] = "0" * 64
        manifest.write_text(json.dumps(payload))
        response = self.request("/api/textoff/comparison", comparisonMode="check", scope="check")
        self.assertEqual(len(json.loads(response.body)["pages"]), 2)
        self.assertEqual(self.image("page-b.png"), b"level1-page-b.png")

    def test_check_roi_still_reads_persisted_check_manifest(self):
        path = (self.manga / "FLUXO_SECUNDARIO/04_TEXTO_OFF/04_AUTO_CLEANER_CHECK/1/"
                "auto-cleaner-check-manifest.json")
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({
            "schema": "textoff_auto_cleaner_check_manifest_v1", "version": 1,
            "provider": "ridi", "manga": "obra", "chapter": "1",
            "source_snapshot": {},
            "approved_occurrences": [{"id": "curated", "page": "page-b.png", "origin": "MANUAL",
                                      "box_normalized": {"left": .1, "top": .2, "width": .3, "height": .4}}],
        }))
        saved = path.read_bytes()
        response = self.request("/api/textoff/residue-occurrences", page="page-b.png",
                                scope="check", comparisonMode="check")
        self.assertEqual(response.status, 200, response.body)
        payload = json.loads(response.body)
        self.assertTrue(payload["decision_persisted"])
        self.assertEqual([row["id"] for row in payload["occurrences"]], ["curated"])
        self.assertEqual(path.read_bytes(), saved)


if __name__ == "__main__":
    unittest.main()
