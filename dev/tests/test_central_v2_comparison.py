"""Read-only comparison routes preserve input identity and stage provenance."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from urllib.parse import urlencode

from central_v2.backend.routes.router import dispatch_get
from central_v2.backend.orchestration.textoff_merged.stages import LEVEL1, LEVEL2
from central_v2.backend.orchestration.textoff_merged.level2_vision import ALGORITHM
from central_v2.backend.orchestration.textoff_merged.residue_occurrences import update_page


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
        # Some running clients number visible pages from 1; resolve the pair
        # by its version when the ordinal does not match the index.
        one_based = self.request(side="before", page="1", version=page["version"])
        self.assertEqual(one_based.status, 200)
        self.assertEqual(one_based.body, b"original")
        merge = self.manga / "FLUXO_SECUNDARIO/02_MERGE/1"
        merge_manifest = merge / "merge-manifest.json"
        metadata = json.loads(merge_manifest.read_text())
        (merge / "page-two.png").write_bytes(b"original-two")
        metadata["outputs"].append({"file": "page-two.png", "global_start": 10,
                                    "global_end": 20})
        metadata["merged_images"] = 2
        metadata["source_total_height"] = 20
        merge_manifest.write_text(json.dumps(metadata))
        (self.level1 / "clean/page-two_clean.png").write_bytes(b"step-one-two")
        clean_metadata = json.loads(self.manifest.read_text())
        clean_metadata["source_artifacts"].append("page-two.png")
        clean_metadata["clean_artifacts"].append("clean/page-two_clean.png")
        clean_metadata["outputs_total"] = 2
        self.manifest.write_text(json.dumps(clean_metadata))
        pages = json.loads(self.request().body)["pages"]
        self.assertEqual(len(pages), 2)
        one_based_in_range = self.request(side="before", page="1", version=pages[0]["version"])
        self.assertEqual(one_based_in_range.status, 200)
        self.assertEqual(one_based_in_range.body, b"original")
        self.assertEqual(self.request(side="before", page="999", version=pages[0]["version"]).status, 404)
        (self.level1 / "clean/page_clean.png").write_bytes(b"reprocessed")
        self.assertEqual(self.request(side="after", page="0", version=page["version"]).status, 404)

    def test_stage_two_uses_level_one_and_requires_current_predecessor(self):
        target = self.manga / "FLUXO_SECUNDARIO/04_TEXTO_OFF" / LEVEL2 / "1"
        (target / "json").mkdir(parents=True)
        (target / "clean").mkdir()
        (target / "mask").mkdir()
        (target / "clean/page_clean.png").write_bytes(b"step-two")
        (target / "mask/page_text_mask.png").write_bytes(b"mask")
        report_row = {"source": "page.png", "clean": "clean/page_clean.png",
                      "level1_clean": "clean/page_clean.png", "mask": "mask/page_text_mask.png",
                      "changed_pixels": 1, "mask_pixels": 1, "changed_outside_mask": 0}
        (target / "json/level2-report.json").write_text(json.dumps({
            "integrity_ok": True, "pages_analyzed": 1, "pages": [report_row],
        }))
        (target / "json/clean-manifest.json").write_text(json.dumps({
            "algorithm": ALGORITHM, "source_stage": LEVEL1, "integrity_ok": True,
            "source_level1_manifest_sha256": hashlib.sha256(self.manifest.read_bytes()).hexdigest(),
            "source_level1_artifacts": ["clean/page_clean.png"],
            "source_artifacts": ["page.png"], "candidate_source_artifacts": ["page.png"],
            "analyzed_source_artifacts": ["page.png"], "changed_source_artifacts": ["page.png"],
            "unchanged_source_artifacts": [], "page_results": [{key: value for key, value in report_row.items()
                                                                   if key != "changed_outside_mask"}],
            "clean_artifacts": ["clean/page_clean.png"], "changed_artifacts": ["clean/page_clean.png"],
            "mask_artifacts": ["mask/page_text_mask.png"], "report": "json/level2-report.json",
            "pages_total": 1, "analyzed_pages_total": 1, "changed_pages_total": 1,
            "outputs_total": 1, "outcome": "visual_changes",
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

    def test_comparison_aggregates_persisted_counts_once_for_current_step(self):
        from unittest.mock import patch
        from central_v2.backend.routes import textoff_comparison

        pairs = [{"name": f"page-{index}.png", "before": self.manga / "FLUXO_SECUNDARIO/02_MERGE/1/page.png",
                  "after": self.level1 / "clean/page_clean.png"} for index in range(5)]
        manifest = self.manga / "FLUXO_SECUNDARIO/04_TEXTO_OFF/RESIDUE_OCCURRENCES/1/residue-occurrences-manifest.json"
        document = {"provider": "ridi", "obra": "obra", "capitulo": "1"}
        update_page(manifest, document, "page-1.png", "1", [{"id": "a"}, {"id": "b"}])
        update_page(manifest, document, "page-1.png", "2", [{"id": "other-step"}])

        with patch.object(textoff_comparison, "comparison_pairs", return_value=pairs), \
             patch.object(textoff_comparison, "read_manifest", wraps=textoff_comparison.read_manifest) as read:
            response = self.request()

        self.assertEqual(response.status, 200)
        pages = json.loads(response.body)["pages"]
        self.assertEqual([page["residue_occurrence_count"] for page in pages], [0, 2, 0, 0, 0])
        read.assert_called_once()

    def test_comparison_without_manifest_reports_zero_counts(self):
        pages = json.loads(self.request().body)["pages"]
        self.assertTrue(pages)
        self.assertTrue(all(page["residue_occurrence_count"] == 0 for page in pages))

    def test_triptych_response_binds_three_stage_images_and_level2_status(self):
        from unittest.mock import patch
        from central_v2.backend.routes import textoff_comparison
        paths = []
        for label in ("original", "level1", "level2"):
            path = self.root / f"{label}.png"
            path.write_bytes(label.encode())
            paths.append(path)
        page = {"name": "page.png", "original": paths[0], "level1": paths[1],
                "level2": paths[2], "level2_status": "changed",
                "level2_chapter_status": "processed"}
        with patch.object(textoff_comparison, "comparison_triplets", return_value=[page]):
            response = self.request("1", layout="triptych")
            self.assertEqual(response.status, 200)
            result = json.loads(response.body)["pages"][0]
            self.assertEqual(result["level2_status"], "changed")
            self.assertEqual(result["level2_chapter_status"], "processed")
            for side, expected in zip(("original", "level1", "level2"),
                                      (b"original", b"level1", b"level2")):
                image = self.request("1", layout="triptych", side=side, page=result["id"],
                                     version=result["version"])
                self.assertEqual(image.body, expected)

    def test_triptych_does_not_hide_a_missing_required_artifact(self):
        from unittest.mock import patch
        from central_v2.backend.routes import textoff_comparison
        with patch.object(textoff_comparison, "comparison_triplets",
                          side_effect=OSError("imagem obrigatória ausente")):
            response = self.request("1", layout="triptych")
        self.assertEqual(response.status, 500)
        self.assertIn("Não foi possível carregar", response.body.decode())

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
