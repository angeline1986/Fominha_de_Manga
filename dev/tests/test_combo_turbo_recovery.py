import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from central_v2.backend.orchestration.combo_turbo import job_api, job_store
from central_v2.backend.orchestration.combo_turbo.api_contract import request_context
from central_v2.backend.orchestration.combo_turbo.run_result_store import (
    new_run_id, new_run_result, set_chapter_result, write_result,
)
from central_v2.backend.routes.router import dispatch_get, dispatch_post


class ComboRecoveryTests(unittest.TestCase):
    def test_only_matching_interrupted_result_can_resume(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            output = root / "output"
            manga = output / "comix/Series"
            image = manga / "IMG/12/page.png"
            image.parent.mkdir(parents=True)
            image.write_bytes(b"source")
            state_root = root / "jobs"
            with patch.object(job_store, "STATE_ROOT", state_root):
                request = {"provider": "comix", "manga": "Series", "chapters": ["12"]}
                token = json.loads(dispatch_post("/api/combo-turbo/plan", request,
                                     output).body)["plan_token"]
                context = request_context(request, output,
                                          fields={"provider", "manga", "chapters"})
                job_id, run_id = "b" * 32, new_run_id()
                folder = state_root / "runs" / job_id
                folder.mkdir(parents=True)
                (folder / ".combo-workspace.json").write_text(json.dumps({
                    "source": str(context["manga"]), "provider": "comix", "chapters": ["12"],
                    "signature": context["signature"], "run_id": run_id}))
                record = new_run_result(run_id, "comix", manga, ["12"], folder,
                                        context["signature"])
                write_result(folder, record)
                job_store.ensure_area("jobs")
                job_store.save({"id": job_id, "status": "running", "provider": "comix",
                    "manga": "Series", "chapters": ["12"], "source": str(manga),
                    "source_signature": context["signature"], "stage": "GLASS",
                    "pages_total": 1, "pages_completed": 0, "pages_blocked": 0,
                    "errors": [], "created_at": "now"})

                def runner(source, provider, chapters, workspace, *, mode, progress=None):
                    if mode == "PLAN_ONLY":
                        return {"plan": {"chapters": [{"chapter": "12", "pages": []}]}}
                    self.assertEqual(Path(workspace), folder.resolve())
                    done = new_run_result(run_id, provider, source, chapters, folder,
                                          context["signature"])
                    done["status"] = "COMPLETED"
                    set_chapter_result(done, {"chapter": "12", "status": "NO_WORK",
                                              "pages": [], "errors": []})
                    write_result(folder, done)
                    return done

                def immediate(operation, *, job_id, **_kwargs):
                    operation(lambda *_args: None, job_id)

                payload = {**request, "plan_token": token, "resume_job_id": job_id}
                with patch.object(job_api, "run_combo", side_effect=runner), \
                     patch.object(job_api, "submit", side_effect=immediate):
                    response = dispatch_post("/api/combo-turbo/jobs", payload, output)
                body = json.loads(response.body)
                self.assertEqual(body["job"]["id"], job_id)
                self.assertEqual(json.loads(dispatch_get(body["status_url"], output).body)
                                 ["job"]["status"], "completed")
                result_url = body["result_url"]
                self.assertEqual(dispatch_get(result_url, output).status, 200)
                image.write_bytes(b"changed source")
                stale = dispatch_get(result_url, output)
                self.assertEqual(stale.status, 409)
                self.assertEqual(json.loads(stale.body)["status"], "STALE")
                image.write_bytes(b"source")
                envelope_path = folder / "combo-run-result.json"
                envelope = json.loads(envelope_path.read_text())
                envelope["result"]["status"] = "tampered"
                envelope_path.write_text(json.dumps(envelope))
                invalid = dispatch_get(result_url, output)
                self.assertEqual(invalid.status, 409)
                self.assertEqual(json.loads(invalid.body)["status"], "INVALID")


if __name__ == "__main__":
    unittest.main()
