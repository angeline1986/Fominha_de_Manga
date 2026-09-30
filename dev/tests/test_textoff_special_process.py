"""Timeout and offline process contracts for the isolated preview worker."""
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from central_v2.backend.orchestration.textoff_special import process


class WorkerProcessTests(unittest.TestCase):
    def test_launch_uses_feature_python_and_offline_environment(self):
        child = MagicMock()
        child.wait.return_value = 0
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with patch.object(process, "python_for", return_value=Path("isolated-python")), \
                 patch.object(process.subprocess, "Popen", return_value=child) as start:
                process.run_worker("transparente", root / "request.json", root / "worker.log")
            command = start.call_args.args[0]
            self.assertEqual(command[0], "isolated-python")
            self.assertIn("central_v2.backend.orchestration.textoff_special.worker", command)
            self.assertEqual(start.call_args.kwargs["env"]["HF_HUB_OFFLINE"], "1")
            self.assertEqual(start.call_args.kwargs["env"]["TRANSFORMERS_OFFLINE"], "1")

    def test_timeout_requests_worker_cleanup_before_returning_failure(self):
        child = MagicMock()
        child.wait.side_effect = [subprocess.TimeoutExpired("worker", 1), 143]
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with patch.object(process, "python_for", return_value=Path("isolated-python")), \
                 patch.object(process.subprocess, "Popen", return_value=child):
                with self.assertRaises(subprocess.TimeoutExpired):
                    process.run_worker("transparente", root / "request.json", root / "worker.log", timeout=1)
            child.terminate.assert_called_once()
            self.assertEqual(child.wait.call_args.kwargs, {"timeout": 15})

    def test_nonzero_exit_is_not_a_successful_preview(self):
        child = MagicMock()
        child.wait.return_value = 1
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with patch.object(process, "python_for", return_value=Path("isolated-python")), \
                 patch.object(process.subprocess, "Popen", return_value=child):
                with self.assertRaisesRegex(RuntimeError, "falhou"):
                    process.run_worker("transparente", root / "request.json", root / "worker.log")


if __name__ == "__main__":
    unittest.main()
