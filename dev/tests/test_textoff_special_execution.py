"""Preview lifecycle: immutable inputs, failed workers and staged outputs."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from central_v2.backend.orchestration.textoff_special import execution
from central_v2.backend.orchestration.textoff_special.artifacts import read_json, sha256, write_json


class PreviewExecutionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manga = self.root / "manga"
        folder = self.manga / "FLUXO_SECUNDARIO/04_TEXTO_OFF/MERGED_NIVEL_I/3"
        (folder / "clean").mkdir(parents=True)
        (folder / "json").mkdir()
        self.source = folder / "clean/page_clean.png"
        self.source.write_bytes(b"immutable image fixture")
        write_json(folder / "json/clean-manifest.json", {
            "integrity_ok": True, "source_stage": "MERGE", "clean_artifacts": ["clean/page_clean.png"],
        })
        self.payload = {"treatment": "transparente_legacy", "level": "MERGED_NIVEL_I",
                        "chapter": "3", "filename": self.source.name,
                        "expected_sha256": sha256(self.source),
                        "selections": [{"x": 1, "y": 1, "width": 3, "height": 4}]}
        self.staging = self.root / "staging"

    def fake_worker(self, key, request, log):
        folder = request.parent
        result = folder / "treatment/result.png"
        result.parent.mkdir()
        result.write_bytes(b"preview fixture")
        write_json(folder / "worker-result.json", {
            "result_file": "treatment/result.png", "validation": {"result_sha256": sha256(result)},
        })

    def run_preview(self, worker=None):
        with patch.object(execution, "python_for", return_value=Path("worker-python")), \
             patch.object(execution, "run_worker", side_effect=worker or self.fake_worker):
            return execution.preview(self.manga, self.payload, staging=self.staging)

    def test_success_stages_result_without_promotion(self):
        result = self.run_preview()
        self.assertEqual(result["execution_status"], "succeeded")
        self.assertFalse(result["promotion_allowed"])
        self.assertEqual(result["visual_review_status"], "pending")
        self.assertEqual(sha256(self.source), self.payload["expected_sha256"])
        self.assertEqual(read_json(self.staging / result["run_id"] / "manifest.json"), result)

    def test_worker_failure_is_persisted_with_no_valid_result(self):
        def fail(*_args):
            raise RuntimeError("worker failed")
        result = self.run_preview(fail)
        self.assertEqual(result["execution_status"], "failed")
        self.assertNotIn("result_file", result)
        self.assertIn("worker failed", result["error"]["error"])

    def test_concurrent_source_change_invalidates_preview(self):
        def stale(*args):
            self.fake_worker(*args)
            self.source.write_bytes(b"changed by another operation")
        result = self.run_preview(stale)
        self.assertEqual(result["execution_status"], "failed")
        self.assertIn("OBSOLETA", result["error"]["error"])

    def test_result_symlink_outside_staging_is_rejected(self):
        def escape(key, request, log):
            (request.parent / "escape.png").symlink_to(self.source)
            write_json(request.parent / "worker-result.json", {
                "result_file": "escape.png", "validation": {"result_sha256": sha256(self.source)},
            })
        result = self.run_preview(escape)
        self.assertEqual(result["execution_status"], "failed")

    def test_staging_cannot_be_inside_work(self):
        self.staging = self.manga / "staging"
        with self.assertRaisesRegex(ValueError, "fora da obra"):
            self.run_preview()

    def test_approved_mode_requires_explicit_backend_keyword(self):
        self.payload["treatment"] = "degrade"
        self.payload["approved_check_rois"] = True
        ordinary = self.run_preview()
        ordinary_request = read_json(self.staging / ordinary["run_id"] / "request.json")
        self.assertNotIn("approved_check_rois", ordinary_request)
        with patch.object(execution, "python_for", return_value=Path("worker-python")), \
             patch.object(execution, "run_worker", side_effect=self.fake_worker):
            approved = execution.preview(self.manga, self.payload, staging=self.staging,
                                         approved_check_rois=True)
        approved_request = read_json(self.staging / approved["run_id"] / "request.json")
        self.assertIs(approved_request["approved_check_rois"], True)


if __name__ == "__main__":
    unittest.main()
