import json
import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from central_v2.backend.orchestration.combo_turbo import orchestrator, planner


class ComboPlannerTests(unittest.TestCase):
    def test_plan_only_info_volume_is_chapter_scoped_for_one_and_forty(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "Series"
            root.mkdir()
            report = root / "json" / "level1-balloon-report.json"
            report.parent.mkdir()
            report.write_text(json.dumps({"pages": [
                {"source": "one.png", "transparent_balloons": [{}]}]}))
            review = {"pages": ["one.png"], "results": {
                stage: [{"page": "one.png", "status": "MISSING", "reasons": []}]
                for stage in ("SOLIDOS", "GLASS")}}
            runs = []
            for chapters in (["01"], [f"{number:02}" for number in range(1, 41)]):
                with (patch.object(planner, "validate_chapter", return_value=review),
                      patch.object(planner, "rows_for", return_value=([{"page": "one.png"}], "hash")),
                      patch.object(planner, "stage_chapter", return_value=report.parent.parent),
                      contextlib.redirect_stdout(io.StringIO()) as output):
                    planner.plan_combo(root, "comix", chapters)
                lines = output.getvalue().splitlines()
                runs.append(lines)
                self.assertEqual(sum("INFO" in line for line in lines), len(chapters) + 2)
                self.assertFalse(any("validando artefato" in line for line in lines))
            self.assertEqual(len(runs[0]), 3)
            self.assertEqual(len(runs[1]), 42)

    def test_plan_marks_reuse_pending_and_no_work_by_page(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "Sample"
            root.mkdir()
            l1 = root / "level1"
            l1.mkdir()
            (l1 / "json").mkdir()
            (l1 / "json/level1-balloon-report.json").write_text(json.dumps({"pages": [
                {"source": "one.png", "transparent_balloons": [{}]},
                {"source": "two.png", "transparent_balloons": []}]}))
            summary = {"pages": ["one.png", "two.png"], "results": {
                "SOLIDOS": [{"page": "one.png", "status": "MISSING", "reasons": []},
                            {"page": "two.png", "status": "MISSING", "reasons": []}],
                "GLASS": [{"page": "one.png", "status": "REUSABLE", "reasons": []},
                          {"page": "two.png", "status": "MISSING", "reasons": []}]}}
            with (patch.object(planner, "validate_chapter", return_value=summary),
                  patch.object(planner, "rows_for", return_value=([{"page": "two.png"}], "hash")),
                  patch.object(planner, "stage_chapter", return_value=l1)):
                plan = planner.plan_chapter(root, "comix", "12")
            self.assertEqual(plan["status"], "PLANNED")
            self.assertEqual(plan["pages"][0]["stages"]["GLASS"]["status"], "REUSED")
            self.assertEqual(plan["pages"][0]["stages"]["SOLIDOS"]["status"], "NO_WORK")
            self.assertEqual(plan["pages"][1]["stages"]["SOLIDOS"]["status"], "PLANNED")
            self.assertEqual(plan["pages"][1]["stages"]["GLASS"]["status"], "NO_WORK")

    def test_duplicate_and_unsafe_chapters_are_blocked(self):
        self.assertEqual(planner.plan_combo(Path("/tmp"), "comix", ["12", "12"])["status"], "BLOCKED")
        self.assertEqual(planner.plan_combo(Path("/tmp"), "comix", ["../12"])["status"], "BLOCKED")


class ComboOrchestratorSafetyTests(unittest.TestCase):
    def test_plan_only_does_not_call_either_engine(self):
        with (patch.object(orchestrator, "plan_combo", return_value={"status": "PLANNED", "chapters": []}),
              patch.object(orchestrator, "run_solids_isolated") as solids,
              patch.object(orchestrator, "run_glass_isolated") as glass):
            result = orchestrator.run_combo("/read-only/source", "comix", ["12"], None)
        self.assertEqual(result["status"], "PLANNED")
        solids.assert_not_called()
        glass.assert_not_called()

    def test_isolated_run_uses_copy_and_rejects_output_inside_source(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "source"
            source.mkdir()
            output = Path(temp) / "experimental"
            plan = {"status": "PLANNED", "chapters": [{"chapter": "12", "pages": []}]}

            def run_on_copy(clone, *_args, **_kwargs):
                self.assertNotEqual(clone.resolve(), source.resolve())
                self.assertTrue(clone.is_dir())
                return {"chapter": "12", "status": "COMPLETED", "pages": [], "errors": []}

            with (patch.object(orchestrator, "plan_combo", return_value=plan),
                  patch.object(orchestrator, "_run_chapter", side_effect=run_on_copy)):
                result = orchestrator.run_combo(source, "comix", ["12"], output, mode="ISOLATED_RUN")
                resumed = orchestrator.run_combo(source, "comix", ["12"], output, mode="ISOLATED_RUN")
            self.assertEqual(result["status"], "COMPLETED")
            self.assertEqual(resumed["status"], "COMPLETED")
            self.assertTrue(output.is_dir())
            self.assertTrue((output / ".combo-workspace.json").is_file())
            self.assertTrue((output / ".combo-workspace" / "source").is_dir())
            input_page = source / "IMG" / "12" / "MERGE" / "page.png"
            input_page.parent.mkdir(parents=True)
            input_page.write_bytes(b"changed source")
            changed = orchestrator.run_combo(source, "comix", ["12"], output, mode="ISOLATED_RUN")
            self.assertEqual(changed["errors"][0]["reason"], "RESUME_SOURCE_CHANGED")
            blocked = orchestrator.run_combo(source, "comix", ["12"], source / "results",
                                             mode="ISOLATED_RUN")
            self.assertEqual(blocked["errors"][0]["reason"], "DISPOSABLE_OUTPUT_REQUIRED")

    def test_blocked_chapter_does_not_discard_other_chapter_result(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "source"
            root.mkdir()
            output = Path(temp) / "isolated-run"
            plan = {"status": "BLOCKED", "chapters": [
                {"chapter": "12", "status": "BLOCKED", "reasons": ["CHECK_MISSING"], "pages": []},
                {"chapter": "13", "status": "PLANNED", "pages": []}]}
            with (patch.object(orchestrator, "plan_combo", side_effect=[plan, plan]),
                  patch.object(orchestrator, "_run_chapter", return_value={
                      "status": "NO_WORK", "pages": [], "errors": []})):
                result = orchestrator.run_combo(root, "comix", ["12", "13"], output,
                                                mode="ISOLATED_RUN")
            self.assertEqual(result["status"], "PARTIAL")
            self.assertEqual([row["status"] for row in result["results"]], ["BLOCKED", "NO_WORK"])

    def test_publisher_receives_only_the_disposable_clone(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "source"
            source = root / "IMG/12/MERGE/page-001.png"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"operational source")
            before = source.read_bytes()
            output = Path(temp) / "isolated"
            plan = {"status": "PLANNED", "chapters": [{"chapter": "12",
                "status": "PLANNED", "pages": [{"page": "page-001.png",
                    "eligible": {"SOLIDOS": False, "GLASS": False}, "stages": {}}]}]}
            raw = {"chapter": "12", "status": "COMPLETED", "errors": [], "pages": [
                {"page": "page-001.png", "status": "COMPOSED", "composition": {}}]}
            def chapter_runner(_clone, _provider, _chapter, chapter_plan, _destination,
                               _progress, page_callback=None):
                page_callback(raw["pages"][0], chapter_plan["pages"][0])
                return raw
            with (patch.object(orchestrator, "plan_combo", side_effect=[plan, plan]),
                  patch.object(orchestrator, "_run_chapter", side_effect=chapter_runner),
                  patch("central_v2.backend.orchestration.combo_turbo.publication.publish_combo",
                        return_value={"status": "PUBLISHED"}) as publish):
                result = orchestrator.run_combo(root, "comix", ["12"], output,
                                                mode="ISOLATED_RUN")
            clone = Path(publish.call_args.args[0])
            self.assertTrue(clone.is_relative_to((output / ".combo-workspace").resolve()))
            self.assertNotEqual(clone.resolve(), root.resolve())
            self.assertEqual(source.read_bytes(), before)
            self.assertEqual(result["publication"][0]["status"], "PUBLISHED")


if __name__ == "__main__":
    unittest.main()
