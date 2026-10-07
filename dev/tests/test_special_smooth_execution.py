"""Check-bound Suave grouping, retry, progress, and staged persistence."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from central_v2.backend.orchestration.textoff_merged.auto_cleaner_check_manifest import (
    SCHEMA as CHECK_SCHEMA, manifest_path as check_path,
)
from central_v2.backend.orchestration.textoff_merged.special_smooth_input import pending_pages
from central_v2.backend.orchestration.textoff_merged.special_smooth_execution import execute_smooth
from central_v2.backend.orchestration.textoff_merged.special_smooth_output import (
    MANIFEST, STAGE, persist_smooth,
)
from central_v2.backend.orchestration.textoff_merged.special_treatments_query import query_special_treatments
from central_v2.backend.orchestration.textoff_merged.special_treatments_manifest import (
    rebuild_special_treatments, manifest_path as special_path,
)
from central_v2.backend.orchestration.textoff_merged.stages import stage_chapter
from central_v2.backend.orchestration.textoff_special.artifacts import sha256
from central_v2.backend.orchestration.textoff_special.catalog import treatment_for


ROWS = [
    ("013-016", 275, 395, 453, 151),
    ("033-037", 175, 2496, 586, 123), ("033-037", 111, 285, 524, 146),
    ("033-037", 215, 5774, 560, 148), ("033-037", 37, 117, 396, 105),
    ("033-037", 227, 6618, 574, 128),
    ("037-042", 142, 5630, 656, 213),
    ("078-082", 385, 3792, 479, 171), ("078-082", 96, 3489, 461, 162),
    ("078-082", 54, 1286, 515, 133), ("082-086", 257, 3551, 463, 179),
]


class SmoothExecutionTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manga = self.root / "comix/Example"
        (self.manga / "IMG/1").mkdir(parents=True)
        rows = [{"id": f"smooth-{i}", "page": f"page-{page}.png",
                 "tipo": "residuo_gradiente", "box_normalized": {
                     "left": .1, "top": .1, "width": .2, "height": .05},
                 "box_pixels": {"x": x, "y": y, "width": width, "height": height}}
                for i, (page, x, y, width, height) in enumerate(ROWS)]
        self.check = check_path(self.manga, "1")
        self.check.parent.mkdir(parents=True)
        self.check.write_text(json.dumps({"schema": CHECK_SCHEMA, "version": 1,
            "provider": "comix", "manga": "Example", "chapter": "1",
            "source_snapshot": {}, "approved_occurrences": rows}), encoding="utf-8")
        rebuild_special_treatments(self.manga, {"provider": "comix", "obra": "Example",
                                                "capitulo": "1"}, "1")
        self.special = special_path(self.manga, "1")

    def test_all_eleven_check_boxes_group_into_five_pages(self):
        _, _, _, groups = pending_pages(self.manga, "comix", "1")
        self.assertEqual({page: len(rows) for page, rows in groups.items()}, {
            "page-013-016.png": 1, "page-033-037.png": 5, "page-037-042.png": 1,
            "page-078-082.png": 3, "page-082-086.png": 1,
        })

    def test_retry_selects_failed_only(self):
        payload = json.loads(self.special.read_text(encoding="utf-8"))
        payload["treatments"]["gradiente_suave"][1]["status"] = "failed"
        self.special.write_text(json.dumps(payload), encoding="utf-8")
        _, _, _, groups = pending_pages(self.manga, "comix", "1", retry=True)
        self.assertEqual(list(groups), ["page-033-037.png"])
        self.assertEqual(len(groups["page-033-037.png"]), 1)

    def test_executor_groups_one_worker_per_page_and_isolates_page_failure(self):
        calls, checkpoints = [], []

        def select(_manga, chapter, page):
            return {"provider": "comix", "manga": "Example", "chapter": chapter,
                    "page": page, "selected_from": "TO_MERGED_NIVEL_I", "level": "MERGED_NIVEL_I",
                    "filename": Path(page).stem + "_clean.png", "path": str(self.check),
                    "sha256": "input-hash", "consolidated_manifest": str(self.check),
                    "consolidated_manifest_sha256": "manifest-hash"}

        def preview(_manga, payload):
            calls.append(payload)
            if payload["chapter"] == "1" and len(payload["selections"]) == 5:
                return {"execution_status": "failed", "error": "ROIs expandidas sobrepostas"}
            return {"execution_status": "succeeded", "run_id": f"run{len(calls)}"}

        def persist(_manga, _provider, _chapter, _path, _digest, page_runs, **_kwargs):
            self.assertEqual(len(page_runs), 4)
            return {item["source"]["page"]: {
                "status": "processed", "output": {"artifact": "clean/out.png", "sha256": "out"},
                "run_id": item["run"]["run_id"],
            } for item in page_runs}

        with patch("central_v2.backend.orchestration.textoff_merged.special_smooth_execution.selected_input",
                   side_effect=select), \
             patch("central_v2.backend.orchestration.textoff_merged.special_smooth_execution.preview",
                   side_effect=preview), \
             patch("central_v2.backend.orchestration.textoff_merged.special_smooth_execution.persist_smooth",
                   side_effect=persist), \
             patch("central_v2.backend.orchestration.textoff_merged.special_smooth_execution.promote_treatment_pages"):
            outcome = execute_smooth(self.manga, "comix", ["1"],
                                     lambda _chapter, event: checkpoints.append(event))
        self.assertEqual([len(call["selections"]) for call in calls], [1, 5, 1, 3, 1])
        self.assertEqual(outcome[0]["status"], "failed")
        self.assertIn("ROIs expandidas", outcome[0].get("error", ""))
        self.assertEqual([event["percent"] for event in checkpoints
                          if event["stage"] == "smooth" and event["percent"]],
                         [20, 40, 60, 80, 100])
        payload = json.loads(self.special.read_text(encoding="utf-8"))
        states = {row["page"]: row["status"]
                  for row in payload["treatments"]["gradiente_suave"]}
        self.assertEqual(states["page-033-037.png"], "failed")
        self.assertEqual(states["page-078-082.png"], "processed")
        summary = query_special_treatments(self.manga, "comix", "gradiente_suave")
        self.assertEqual(summary["chapters"][0]["status"], "failed")

    def test_expansion_overlap_on_five_roi_page_is_rejected_by_algorithm_contract(self):
        first, second = (ROWS[4], ROWS[2])
        expanded = []
        for _, x, y, width, height in (first, second):
            amount = max(12, round(height * .35))
            expanded.append((max(12, x - amount), max(12, y - amount),
                             min(928, x + width + amount), min(8147, y + height + amount)))
        a, b = expanded
        self.assertLess(max(a[0], b[0]), min(a[2], b[2]))
        self.assertLess(max(a[1], b[1]), min(a[3], b[3]))

    def test_persistence_writes_separate_stage_and_report(self):
        source = self.root / "input.png"
        source.write_bytes(b"source")
        consolidated = self.root / "consolidated.json"
        consolidated.write_text("{}", encoding="utf-8")
        preview_root = self.root / "previews"
        run_id = "ab12cd34"
        treatment_folder = preview_root / run_id / "treatment"
        treatment_folder.mkdir(parents=True)
        result = treatment_folder / "gradiente_suave.png"
        result.write_bytes(b"smooth output")
        report = treatment_folder / "gradiente_suave_report.json"
        report.write_text('{"regions": []}\n', encoding="utf-8")
        special_hash = sha256(self.special)
        item_source = {"provider": "comix", "manga": "Example", "chapter": "1",
                       "page": "page-013-016.png", "selected_from": "TO_MERGED_NIVEL_II",
                       "path": str(source), "sha256": sha256(source),
                       "consolidated_manifest": str(consolidated),
                       "consolidated_manifest_sha256": sha256(consolidated)}
        run = {"execution_status": "succeeded", "run_id": run_id,
               "result_file": "treatment/gradiente_suave.png",
               "source": {"sha256": item_source["sha256"]},
               "treatment": {"algorithm": treatment_for("gradiente_suave").algorithm},
               "validation": {"result_sha256": sha256(result), "changed_pixels": 3}}
        item = {"source": item_source, "run": run, "ids": ["smooth-0"],
                "rois": [{"x": 275, "y": 395, "width": 453, "height": 151}],
                "special_path": self.special, "special_hash": special_hash,
                "check_path": self.check, "check_hash": sha256(self.check)}
        with patch("central_v2.backend.orchestration.textoff_merged.special_smooth_output.STAGING_ROOT",
                   preview_root):
            records = persist_smooth(self.manga, "comix", "1", self.special,
                                     special_hash, [item], check_path=self.check,
                                     check_hash=sha256(self.check))
        target = stage_chapter(self.manga, STAGE, "1", read_legacy=False)
        payload = json.loads((target / "json" / MANIFEST).read_text(encoding="utf-8"))
        self.assertEqual(records["page-013-016.png"]["status"], "processed")
        self.assertEqual(payload["pages"]["page-013-016.png"]["algorithm"],
                         treatment_for("gradiente_suave").algorithm)
        self.assertTrue((target / "clean/page-013-016_suave.png").is_file())
        self.assertTrue((target / "json/page-013-016_gradiente_suave_report.json").is_file())


if __name__ == "__main__":
    unittest.main()
