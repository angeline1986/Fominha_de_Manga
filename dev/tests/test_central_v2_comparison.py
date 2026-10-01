"""Read-only comparison routes preserve input identity and stage provenance."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from urllib.parse import urlencode

from central_v2.backend.routes.router import dispatch_get
from central_v2.backend.orchestration.textoff_merged.stages import LEVEL1, LEVEL2


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manga = self.root / "ridi/obra"
        (self.manga / "IMG/1").mkdir(parents=True)
        merge = self.manga / "FLUXO_SECUNDARIO/02_MERGE/1"
        merge.mkdir(parents=True)
        (merge / "page.png").write_bytes(b"original")
        (merge / "merge-manifest.json").write_text(json.dumps({
            "merged_images": 1, "source_total_height": 10,
            "outputs": [{"file": "page.png", "global_start": 0, "global_end": 10}],
        }))
        self.level1 = self.manga / "FLUXO_SECUNDARIO/04_TEXTO_OFF" / LEVEL1 / "1"
        (self.level1 / "clean").mkdir(parents=True)
        (self.level1 / "json").mkdir()
        (self.level1 / "clean/page_clean.png").write_bytes(b"step-one")
        self.manifest = self.level1 / "json/clean-manifest.json"
        self.manifest.write_text(json.dumps({
            "source_stage": "MERGE", "integrity_ok": True, "source_artifacts": ["page.png"],
            "clean_artifacts": ["clean/page_clean.png"], "outputs_total": 1,
        }))

    def request(self, step="1", **options):
        params = dict(provider="ridi", manga="obra", chapter="1", step=step)
        params.update(options)
        suffix = "/image" if "side" in options else ""
        return dispatch_get("/api/textoff/comparison" + suffix + "?" + urlencode(params), self.root)

    def test_stage_one_pair_and_changed_result_rejection(self):
        response = self.request()
        self.assertEqual(response.status, 200)
        page = json.loads(response.body)["pages"][0]
        for side, expected in [("before", b"original"), ("after", b"step-one")]:
            result = self.request(side=side, page=page["id"], version=page["version"])
            self.assertEqual(result.body, expected)
        (self.level1 / "clean/page_clean.png").write_bytes(b"reprocessed")
        self.assertEqual(self.request(side="after", page="0", version=page["version"]).status, 404)

    def test_stage_two_uses_level_one_and_requires_current_predecessor(self):
        target = self.manga / "FLUXO_SECUNDARIO/04_TEXTO_OFF" / LEVEL2 / "1"
        (target / "json").mkdir(parents=True)
        (target / "clean").mkdir()
        (target / "clean/page_clean.png").write_bytes(b"step-two")
        (target / "json/clean-manifest.json").write_text(json.dumps({
            "source_stage": LEVEL1, "integrity_ok": True,
            "source_level1_manifest_sha256": hashlib.sha256(self.manifest.read_bytes()).hexdigest(),
            "source_artifacts": ["page.png"], "candidate_source_artifacts": ["page.png"],
            "clean_artifacts": ["clean/page_clean.png"], "changed_artifacts": ["clean/page_clean.png"],
            "pages_total": 1,
        }))
        page = json.loads(self.request("2").body)["pages"][0]
        for side, expected in [("before", b"step-one"), ("after", b"step-two")]:
            self.assertEqual(self.request("2", side=side, page="0", version=page["version"]).body, expected)
        self.manifest.write_text(self.manifest.read_text() + " ")
        self.assertEqual(json.loads(self.request("2").body)["pages"], [])

    def test_rejects_traversal_unknown_steps_and_unavailable_results(self):
        for params in [{"chapter": ".."}, {"chapter": "../1"}, {"step": "8"}, {"manga": "../obra"}]:
            self.assertEqual(self.request(**params).status, 404)
        self.assertEqual(json.loads(self.request("3").body)["pages"], [])
        self.assertEqual(self.request(side="before", page="999", version="bad").status, 404)

    def test_experimental_comparison_uses_matching_step_and_latest_snapshot(self):
        from unittest.mock import patch
        from central_v2.backend.orchestration.textoff_merged import comparison
        staging = self.root / "staging"
        records = []
        for step, run_id, date in [("ac3", "old", "2026-01-01"),
                                   ("ac3", "new", "2026-01-02"),
                                   ("ac4", "legacy", "2026-01-03")]:
            folder = staging / run_id
            (folder / "input").mkdir(parents=True)
            (folder / "input/source.png").write_bytes(b"snapshot")
            (folder / "result.png").write_bytes(run_id.encode())
            records.append((step, {"run_id": run_id, "finished_at": date, "result_file": "result.png",
                                   "source": {"chapter": "1", "filename": "page_clean.png",
                                              "sha256": hashlib.sha256(b"snapshot").hexdigest()}}))
        with patch.object(comparison, "STAGING_ROOT", staging), \
             patch.object(comparison, "current_preview_records", return_value=records):
            for step, expected in [("3", b"new"), ("4", b"legacy")]:
                pair = comparison.comparison_pairs(self.manga, "1", step)[0]
                self.assertEqual(pair["before"].read_bytes(), b"snapshot")
                self.assertEqual(pair["after"].read_bytes(), expected)
            (staging / "new/input/source.png").write_bytes(b"tampered")
            self.assertEqual(comparison.comparison_pairs(self.manga, "1", "3"), [])
