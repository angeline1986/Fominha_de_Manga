"""Execution route accepts intentions, never paths or ROIs."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

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
                "approved_occurrences": [{"id": f"approved-{chapter}", "page": "page.png",
                    "tipo": "residuo_degrade", "box_normalized": {
                        "left": .1, "top": .1, "width": .2, "height": .2},
                    "box_pixels": {"x": 10, "y": 20, "width": 30, "height": 40}}],
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
                   return_value={"id": "job"}) as submit:
            response = self.request()
            self.assertEqual(response.status, 202)
            self.assertEqual(submit.call_args.kwargs["total"], 1)
            with patch("central_v2.backend.routes.special_treatments.execute_degrade",
                       return_value=[]) as execute:
                submit.call_args.args[0](lambda *_: None, "job")
            self.assertEqual(execute.call_args.args[2], ["1"])

    def test_other_treatments_paths_and_empty_selection_rejected(self):
        with patch("central_v2.backend.routes.special_treatments.submit") as submit:
            for payload in ({"treatment": "estilizado"}, {"treatment": "gradiente_suave"},
                            {"chapters": []}, {"chapters": ["../1"]},
                            {"chapters": ["1", "1"]}, {"rois": [{"x": 0}]},
                            {"path": "/tmp/arbitrary.png"},
                            {"approved_check_rois": True}):
                response = self.request(**payload)
                self.assertEqual(response.status, 400, payload)
            submit.assert_not_called()

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


if __name__ == "__main__":
    unittest.main()
