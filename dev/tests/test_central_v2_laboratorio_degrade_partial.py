"""A successful Degradê preview can still contain deferred selected components."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from central_v2.backend.orchestration.textoff_special.artifacts import sha256, write_json
from central_v2.backend.routes import laboratorio_degrade as route
from central_v2.backend.routes import laboratorio_degrade_jobs as jobs
from central_v2.backend.routes.response import RouteResponse


def response(body, status=200):
    return RouteResponse(status, json.dumps(body).encode("utf-8"))


class PartialDegradeTests(unittest.TestCase):
    def test_successful_run_offers_deferred_components_inside_selected_roi(self):
        with TemporaryDirectory() as temp:
            folder = Path(temp)
            source = folder / "source.png"
            source.write_bytes(b"source")
            report = folder / "treatment/balloon_authorization.json"
            report.parent.mkdir()
            write_json(report, {"pages": [{"source": "source.png",
                "component_decisions": [{"component": 1, "bbox": [10, 10, 20, 20],
                    "area": 120, "reason": "transparent_balloon_deferred"}]}]})
            mask = folder / "treatment/cleaner/source_mask_raw.png"
            mask.parent.mkdir()
            mask.write_bytes(b"mask")
            run_id = "a" * 32
            write_json(folder / "manifest.json", {"run_id": run_id,
                "execution_status": "succeeded"})
            write_json(folder / "request.json", {"run_id": run_id,
                "treatment": "degrade", "source": {"path": str(source),
                "sha256": sha256(source)}, "selections": [
                    {"x": 0, "y": 0, "width": 40, "height": 40}]})
            with patch.object(route, "folder_for_request", return_value=(folder, folder)), \
                    patch.object(route, "belongs_to_manga", return_value=True):
                result = route.authorization_candidates({"run_id": run_id}, folder)
            self.assertEqual(result.status, 200)
            self.assertEqual(json.loads(result.body)["candidates"][0]["component"], 1)

    def test_successful_partial_run_retries_with_eligible_deferred_components(self):
        run_id = "a" * 32
        responses = []

        def submit(operation, total):
            responses.extend(operation(lambda *_: None, "job"))
            return "job"

        with patch.object(jobs, "submit", side_effect=submit), \
                patch.object(jobs, "execute", return_value=response({"run_id": run_id})), \
                patch.object(jobs, "authorization_candidates", return_value=response({
                    "proposal_run_id": run_id, "proposal_token": "token",
                    "candidates": [{"id": "first"}, {"id": "second"}]})) as candidates, \
                patch.object(jobs, "confirm_authorization", return_value=response({
                    "run_id": "b" * 32, "image_url": "/result"})) as confirm:
            self.assertEqual(jobs.start({"chapter": "28"}, Path("/tmp")).status, 202)
        candidates.assert_called_once()
        self.assertEqual(confirm.call_args.args[0]["component_ids"], ["first", "second"])
        self.assertEqual(responses[0]["run_id"], "b" * 32)
        self.assertEqual(responses[0]["status"], "succeeded")


if __name__ == "__main__":
    unittest.main()
