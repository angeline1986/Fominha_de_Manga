"""Execution route accepts intentions, never paths or ROIs."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from central_v2.backend.orchestration.textoff_special.artifacts import sha256
from central_v2.backend.orchestration.textoff_merged.auto_cleaner_check_manifest import (
    SCHEMA as CHECK_SCHEMA, manifest_path as check_path,
)
from central_v2.backend.orchestration.textoff_merged.special_treatments_manifest import rebuild_special_treatments
from central_v2.backend.routes.router import dispatch_post


class DegradeRouteTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name)
        self.manga = self.output / "comix" / "Example"
        for chapter in ("1", "2"):
            (self.manga / "IMG" / chapter).mkdir(parents=True)
            check = check_path(self.manga, chapter)
            check.parent.mkdir(parents=True)
            check.write_text(json.dumps({
                "schema": CHECK_SCHEMA, "version": 1, "provider": "comix",
                "manga": "Example", "chapter": chapter, "source_snapshot": {},
                "approved_occurrences": [
                    {"id": f"approved-{chapter}", "page": "page.png",
                     "tipo": "residuo_degrade", "box_normalized": {
                         "left": .1, "top": .1, "width": .2, "height": .2},
                     "box_pixels": {"x": 10, "y": 20, "width": 30, "height": 40}},
                    {"id": f"smooth-{chapter}", "page": "page.png",
                     "tipo": "residuo_gradiente", "box_normalized": {
                         "left": .5, "top": .5, "width": .2, "height": .1},
                     "box_pixels": {"x": 100, "y": 200, "width": 30, "height": 20}},
                ],
            }), encoding="utf-8")
            rebuild_special_treatments(self.manga, {"provider": "comix",
                "obra": "Example", "capitulo": chapter}, chapter)

    def request(self, **changes):
        payload = {"provider": "comix", "manga": "Example",
                   "treatment": "degrade", "chapters": ["1"]}
        payload.update(changes)
        return dispatch_post("/api/textoff/special/treatments/execute", payload, self.output)

    def test_only_selected_chapters_are_submitted(self):
        with patch("central_v2.backend.routes.special_treatments.submit",
                   return_value={"id": "job"}) as submit, \
             patch("central_v2.backend.routes.special_treatments.execute_degrade",
                   return_value=[]) as execute:
            response = self.request()
            self.assertEqual(response.status, 202)
            self.assertEqual(submit.call_args.kwargs["total"], 1)
            submit.call_args.args[0](lambda *_: None, "job")
            self.assertEqual(execute.call_args.args[2], ["1"])

    def test_other_treatments_paths_and_empty_selection_rejected(self):
        with patch("central_v2.backend.routes.special_treatments.submit") as submit:
            for payload in ({"chapters": []}, {"chapters": ["../1"]},
                            {"chapters": ["1", "1"]}, {"rois": [{"x": 0}]},
                            {"path": "/tmp/arbitrary.png"},
                            {"approved_check_rois": True}):
                response = self.request(**payload)
                self.assertEqual(response.status, 400, payload)
            submit.assert_not_called()


    def test_suave_dispatches_its_own_executor(self):
        with patch("central_v2.backend.routes.special_treatments.submit",
                   return_value={"id": "job"}) as submit, \
             patch("central_v2.backend.routes.special_treatments.execute_smooth",
                   return_value=[]) as execute:
            response = self.request(treatment="gradiente_suave")
            self.assertEqual(response.status, 202)
            submit.call_args.args[0](lambda *_: None, "job")
            self.assertEqual(execute.call_args.args[2], ["1"])

    def test_failed_requires_explicit_retry_and_rechecks_check(self):
        from central_v2.backend.orchestration.textoff_merged.special_treatments_manifest import manifest_path
        path = manifest_path(self.manga, "1")
        special = json.loads(path.read_text(encoding="utf-8"))
        for row in special["treatments"]["degrade"]:
            row["status"] = "failed"
        path.write_text(json.dumps(special), encoding="utf-8")
        self.assertEqual(self.request().status, 400)
        with patch("central_v2.backend.routes.special_treatments.submit", return_value={"id": "job"}) as submit:
            self.assertEqual(self.request(retry=True).status, 202)
            self.assertEqual(submit.call_args.kwargs["total"], 1)
        self.assertEqual(self.request(retry="true").status, 400)
        check = check_path(self.manga, "1")
        check.write_text(check.read_text(encoding="utf-8") + " ", encoding="utf-8")
        self.assertEqual(self.request(retry=True).status, 400)

    def test_reexecute_is_separate_from_retry_and_requires_previous_result(self):
        from central_v2.backend.orchestration.textoff_merged.special_treatments_manifest import manifest_path
        path = manifest_path(self.manga, "1")
        special = json.loads(path.read_text(encoding="utf-8"))
        for row in special["treatments"]["degrade"]:
            row["status"] = "processed"
        path.write_text(json.dumps(special), encoding="utf-8")
        with patch("central_v2.backend.routes.special_treatments.submit",
                   return_value={"id": "job"}) as submit, \
             patch("central_v2.backend.routes.special_treatments.execute_degrade") as execute:
            self.assertEqual(self.request(reexecute=True).status, 202)
            submit.call_args.args[0](lambda *_: None, "job")
            self.assertFalse(execute.call_args.kwargs["retry"])
            self.assertTrue(execute.call_args.kwargs["reexecute"])
        self.assertEqual(self.request(retry=True, reexecute=True).status, 400)
        for row in special["treatments"]["degrade"]:
            row["status"] = "pending"
        path.write_text(json.dumps(special), encoding="utf-8")
        self.assertEqual(self.request(reexecute=True).status, 400)

    def test_preparation_rebuilds_from_current_check_and_preserves_old_result_history(self):
        from central_v2.backend.orchestration.textoff_merged.special_reexecution import prepare_reexecution
        from central_v2.backend.orchestration.textoff_merged.special_treatments_manifest import manifest_path
        from central_v2.backend.orchestration.textoff_merged.artifact_paths import artifact_ref
        from central_v2.backend.orchestration.textoff_merged.stages import stage_chapter
        special_path = manifest_path(self.manga, "1")
        special = json.loads(special_path.read_text(encoding="utf-8"))
        row = special["treatments"]["degrade"][0]
        row.update(status="processed", result={"run_id": "old-run", "output": "old.png"})
        special_path.write_text(json.dumps(special), encoding="utf-8")
        check = json.loads(check_path(self.manga, "1").read_text(encoding="utf-8"))
        check["approved_occurrences"][0]["box_pixels"]["x"] = 44
        check_path(self.manga, "1").write_text(json.dumps(check), encoding="utf-8")
        stage = stage_chapter(self.manga, "PINCEL_DEGRADE", "1", read_legacy=False)
        output_ref = artifact_ref("clean", "page_degrade.png")
        output = stage / output_ref
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"previous result")
        stage_manifest = stage / artifact_ref("json", "degrade-manifest.json")
        stage_manifest.parent.mkdir(parents=True, exist_ok=True)
        stage_manifest.write_text(json.dumps({"pages": {"page.png": {"output": {
            "artifact": output_ref, "sha256": sha256(output)}}}}), encoding="utf-8")
        prepare_reexecution(self.manga, "comix", "1", "degrade")
        refreshed = json.loads(special_path.read_text(encoding="utf-8"))
        current = refreshed["treatments"]["degrade"][0]
        self.assertEqual(current["box_pixels"]["x"], 44)
        self.assertEqual(current["status"], "pending")
        self.assertNotIn("result", current)
        self.assertEqual(refreshed["reexecution_history"][-1]["superseded_occurrences"][0]["result"]["run_id"], "old-run")
        operational = json.loads(stage_manifest.read_text(encoding="utf-8"))
        archive = operational["superseded_results"][-1]["pages"][0]["archived_artifacts"][0]["artifact"]
        self.assertFalse(output.exists())
        self.assertEqual((stage / archive).read_bytes(), b"previous result")
        self.assertEqual(operational["pages"], {})

    def test_check_race_after_stage_promotion_rolls_back_both_manifests_and_output(self):
        from central_v2.backend.orchestration.textoff_merged.artifact_paths import artifact_ref
        from central_v2.backend.orchestration.textoff_merged.special_reexecution import prepare_reexecution
        from central_v2.backend.orchestration.textoff_merged import special_reexecution
        from central_v2.backend.orchestration.textoff_merged.special_treatments_manifest import manifest_path
        from central_v2.backend.orchestration.textoff_merged.stages import stage_chapter
        special_path = manifest_path(self.manga, "1")
        special = json.loads(special_path.read_text(encoding="utf-8"))
        special["treatments"]["degrade"][0]["status"] = "processed"
        special_path.write_text(json.dumps(special), encoding="utf-8")
        original_special = special_path.read_bytes()
        stage = stage_chapter(self.manga, "PINCEL_DEGRADE", "1", read_legacy=False)
        output_ref, manifest_ref = artifact_ref("clean", "old.png"), artifact_ref("json", "degrade-manifest.json")
        output = stage / output_ref
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"old output")
        operational_path = stage / manifest_ref
        operational_path.parent.mkdir(parents=True, exist_ok=True)
        operational_path.write_text(json.dumps({"pages": {"page.png": {"output": {
            "artifact": output_ref, "sha256": sha256(output)}}}}), encoding="utf-8")
        original_operational = operational_path.read_bytes()
        check = check_path(self.manga, "1")
        archive = special_reexecution._archive_stage

        def promote_then_change_check(*args):
            archive(*args)
            changed = json.loads(check.read_text(encoding="utf-8"))
            changed["approved_occurrences"][0]["box_pixels"]["x"] += 1
            check.write_text(json.dumps(changed), encoding="utf-8")

        with patch("central_v2.backend.orchestration.textoff_merged.special_reexecution._archive_stage",
                   side_effect=promote_then_change_check):
            with self.assertRaisesRegex(ValueError, "Check mudou"):
                prepare_reexecution(self.manga, "comix", "1", "degrade")
        self.assertEqual(special_path.read_bytes(), original_special)
        self.assertEqual(operational_path.read_bytes(), original_operational)
        self.assertEqual(output.read_bytes(), b"old output")
        self.assertIn('"page.png"', operational_path.read_text(encoding="utf-8"))
        self.assertNotIn("archive", {item.name for item in stage.iterdir()})


if __name__ == "__main__":
    unittest.main()
