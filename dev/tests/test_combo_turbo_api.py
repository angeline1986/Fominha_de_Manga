import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from central_v2.backend.orchestration.combo_turbo import api_contract, job_api, job_store
from central_v2.backend.orchestration.combo_turbo.run_result_store import (
    new_run_id, new_run_result, set_chapter_result, write_result,
)
from central_v2.backend.routes.router import dispatch_get, dispatch_post


class ComboTurboApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.output = self.root / "output"
        self.manga = self.output / "comix" / "Series"
        image = self.manga / "IMG" / "12" / "MERGE" / "page-001.png"
        image.parent.mkdir(parents=True)
        image.write_bytes(b"source")
        (self.manga / "IMG" / "12" / "page-001.png").write_bytes(b"source")
        self.payload = {"provider": "comix", "manga": "Series", "chapters": ["12"]}
        self.state_root = self.root / "jobs"
        self.patches = [patch.object(job_store, "STATE_ROOT", self.state_root)]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.temp.cleanup()

    def test_plan_only_and_request_security(self):
        with patch("central_v2.backend.orchestration.combo_turbo.api_contract.run_combo",
                   return_value={"status": "PLANNED", "plan": {"status": "PLANNED",
                   "chapters": [{"chapter": "12", "status": "PLANNED", "pages": []}]}}):
            response = dispatch_post("/api/combo-turbo/plan", self.payload, self.output)
        body = json.loads(response.body)
        self.assertEqual(response.status, 200)
        self.assertTrue(body["plan_token"])
        for invalid in ({**self.payload, "publish": True},
                        {**self.payload, "chapters": []},
                        {**self.payload, "chapters": ["../12"]},
                        {**self.payload, "chapters": ["12", "12"]},
                        {**self.payload, "provider": "invalid"},
                        {**self.payload, "output_dir": str(self.root)}):
            self.assertEqual(dispatch_post("/api/combo-turbo/plan", invalid,
                             self.output).status, 400)

    def test_symlinked_source_is_rejected(self):
        target = self.root / "external"
        target.mkdir()
        link = self.manga / "IMG/12/external-link"
        link.symlink_to(target, target_is_directory=True)
        response = dispatch_post("/api/combo-turbo/plan", self.payload, self.output)
        self.assertEqual(response.status, 400)

    def test_unknown_job_and_result_return_not_found(self):
        job_id = "0" * 32
        self.assertEqual(dispatch_get(f"/api/combo-turbo/jobs/{job_id}", self.output).status, 404)
        self.assertEqual(dispatch_get(f"/api/combo-turbo/jobs/{job_id}/result",
                                      self.output).status, 404)

    def test_multi_chapter_plan_preserves_independent_states(self):
        chapter = self.manga / "IMG/13/page-001.png"
        chapter.parent.mkdir(parents=True)
        chapter.write_bytes(b"page 13")
        plan = {"status": "BLOCKED", "chapters": [
            {"chapter": "12", "status": "BLOCKED", "pages": [],
             "reasons": ["CHECK_MISSING"]},
            {"chapter": "13", "status": "PLANNED", "pages": []}]}
        with patch.object(api_contract, "run_combo", return_value={
                "status": "BLOCKED", "plan": plan}):
            response = dispatch_post("/api/combo-turbo/plan",
                {**self.payload, "chapters": ["12", "13"]}, self.output)
        summary = json.loads(response.body)["summary"]
        self.assertEqual(summary["chapters_total"], 2)
        self.assertEqual(summary["blocked"], 1)
        self.assertEqual(summary["planned"], 1)
        self.assertTrue(summary["eligible"])

    def test_job_uses_server_workspace_and_persisted_result(self):
        plan_response = dispatch_post("/api/combo-turbo/plan", self.payload, self.output)
        token = json.loads(plan_response.body)["plan_token"]
        request = {**self.payload, "plan_token": token}
        observed = {}

        def fake_run(source, provider, chapters, output, *, mode, progress=None):
            if mode == "PLAN_ONLY":
                return {"status": "PLANNED", "plan": {"status": "PLANNED", "chapters": [
                    {"chapter": "12", "status": "PLANNED", "pages": [{
                        "page": "page-001.png", "eligible": {"SOLIDOS": True, "GLASS": True},
                        "stages": {"SOLIDOS": {"status": "PLANNED", "needed": True},
                                   "GLASS": {"status": "REUSED", "needed": False}}}]}]}}
            observed["output"] = Path(output)
            output = Path(output)
            output.mkdir(parents=True)
            run_id = new_run_id()
            signature = job_api.source_signature(source, provider, chapters)
            (output / ".combo-workspace.json").write_text(json.dumps({
                "source": str(source), "provider": provider, "chapters": chapters,
                "signature": signature, "run_id": run_id}))
            result = new_run_result(run_id, provider, source, chapters, output, signature)
            set_chapter_result(result, {"chapter": "12", "status": "NO_WORK", "pages": [], "errors": []})
            result["status"] = "COMPLETED"
            write_result(output, result)
            return result

        def immediate_submit(operation, **_kwargs):
            operation(lambda *_args: None, "unused")

        with patch.object(job_api, "run_combo", side_effect=fake_run), \
             patch.object(job_api, "submit", side_effect=immediate_submit):
            response = dispatch_post("/api/combo-turbo/jobs", request, self.output)
        body = json.loads(response.body)
        self.assertEqual(response.status, 202, body)
        job_id = body["job"]["id"]
        self.assertEqual(response.status, 202)
        self.assertTrue(observed["output"].is_relative_to(self.state_root.resolve()))
        self.assertFalse(observed["output"].is_relative_to(self.manga))
        status = dispatch_get(body["status_url"], self.output)
        self.assertEqual(json.loads(status.body)["job"]["status"], "completed")
        result = dispatch_get(body["result_url"], self.output)
        payload = json.loads(result.body)
        self.assertEqual(result.status, 200)
        self.assertEqual(payload["result"]["results"][0]["status"], "NO_WORK")

    def test_stale_plan_and_interrupted_job_are_not_reported_completed(self):
        plan = dispatch_post("/api/combo-turbo/plan", self.payload, self.output)
        token = json.loads(plan.body)["plan_token"]
        (self.manga / "IMG/12/MERGE/page-001.png").write_bytes(b"changed")
        response = dispatch_post("/api/combo-turbo/jobs",
            {**self.payload, "plan_token": token}, self.output)
        self.assertEqual(response.status, 409)

        state = {"id": "a" * 32, "status": "running", "provider": "comix",
                 "manga": "Series", "chapters": ["12"], "stage": "GLASS",
                 "pages_total": 1, "pages_completed": 0, "pages_blocked": 0,
                 "created_at": "now", "updated_at": "now", "errors": []}
        job_store.ensure_area("jobs")
        job_store.save(state)
        status = dispatch_get(f"/api/combo-turbo/jobs/{state['id']}", self.output)
        self.assertEqual(json.loads(status.body)["job"]["status"], "interrupted")

    def test_context_changed_while_queued_fails_before_isolated_run(self):
        plan = dispatch_post("/api/combo-turbo/plan", self.payload, self.output)
        request = {**self.payload, "plan_token": json.loads(plan.body)["plan_token"]}
        source = self.manga / "IMG/12/MERGE/page-001.png"

        def change_before_worker(operation, *, job_id, **_kwargs):
            source.write_bytes(b"changed after enqueue")
            operation(lambda *_args: None, job_id)

        with patch.object(job_api, "submit", side_effect=change_before_worker):
            response = dispatch_post("/api/combo-turbo/jobs", request, self.output)
        self.assertEqual(response.status, 202)
        job_id = json.loads(response.body)["job"]["id"]
        status = dispatch_get(f"/api/combo-turbo/jobs/{job_id}", self.output)
        self.assertEqual(json.loads(status.body)["job"]["status"], "failed")

    def test_same_manga_jobs_are_serialized(self):
        plan = dispatch_post("/api/combo-turbo/plan", self.payload, self.output)
        request = {**self.payload, "plan_token": json.loads(plan.body)["plan_token"]}
        try:
            with patch.object(job_api, "submit", return_value={}):
                self.assertEqual(dispatch_post("/api/combo-turbo/jobs", request,
                                 self.output).status, 202)
                self.assertEqual(dispatch_post("/api/combo-turbo/jobs", request,
                                 self.output).status, 400)
        finally:
            job_api._reserved_manga.clear()


if __name__ == "__main__":
    unittest.main()
