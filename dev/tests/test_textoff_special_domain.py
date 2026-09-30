"""Worker-only interpreter binding and independent pixel invariants."""
import sys
import tempfile
from types import SimpleNamespace
import unittest
from pathlib import Path
from unittest.mock import patch

from central_v2.backend.orchestration.textoff_special import catalog, domain
from central_v2.backend.orchestration.textoff_special.verification import verify


class DomainIsolationTests(unittest.TestCase):
    def test_both_nested_executors_use_worker_python_and_restore_binding(self):
        calls = []
        base = SimpleNamespace(CLEANER_PY=Path("old-environment"))
        base._run_cleaner = lambda *args: calls.append(str(base.CLEANER_PY))
        transparent = SimpleNamespace(_run_lama_worker=lambda *args: calls.append(str(base.CLEANER_PY)))

        def run(*_args):
            base._run_cleaner()
            transparent._run_lama_worker()
            return Path("result.png"), {}

        for key in catalog.TREATMENTS:
            adapter = SimpleNamespace(**{catalog.treatment_for(key).function: run})
            with patch.object(domain, "runtime_folder", return_value=Path(sys.prefix).parent), \
                 patch.object(domain.sys, "prefix", str(Path(sys.prefix).parent / ".venv")), \
                 patch.object(domain.importlib, "import_module", side_effect=[base, transparent, adapter]), \
                 patch.object(domain, "write_json"):
                domain.run_treatment(key, Path("input"), Path("target"), [])
            self.assertEqual(calls[-2:], [sys.executable, sys.executable])
            self.assertEqual(base.CLEANER_PY, Path("old-environment"))

    def test_server_process_cannot_call_domain_directly(self):
        with patch.object(domain, "runtime_folder", return_value=Path("/nonexistent/feature")):
            with self.assertRaisesRegex(RuntimeError, "exclusivamente"):
                domain.run_treatment("transparente", Path("in"), Path("out"), [])

    def test_runtime_has_no_fallback_to_other_features(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(catalog, "RUNTIME_ROOT", Path(folder)):
            with self.assertRaisesRegex(RuntimeError, "ausente"):
                catalog.python_for("transparente")
            with self.assertRaises(ValueError):
                catalog.python_for("../merged_nivel_i")

    def test_adapter_failure_restores_interpreter_and_nested_functions(self):
        base = SimpleNamespace(CLEANER_PY=Path("old-environment"), _run_cleaner=lambda: None)
        transparent = SimpleNamespace(_run_lama_worker=lambda: None)
        cleaner, lama = base._run_cleaner, transparent._run_lama_worker

        def fail(*_args):
            raise ValueError("empty mask")

        adapter = SimpleNamespace(run_transparent_roi=fail)
        with patch.object(domain, "runtime_folder", return_value=Path(sys.prefix).parent), \
             patch.object(domain.sys, "prefix", str(Path(sys.prefix).parent / ".venv")), \
             patch.object(domain.importlib, "import_module", side_effect=[base, transparent, adapter]), \
             patch.object(domain, "write_json"):
            with self.assertRaisesRegex(ValueError, "empty mask"):
                domain.run_treatment("transparente", Path("in"), Path("out"), [])
        self.assertEqual(base.CLEANER_PY, Path("old-environment"))
        self.assertIs(base._run_cleaner, cleaner)
        self.assertIs(transparent._run_lama_worker, lama)


class PixelInvariantTests(unittest.TestCase):
    def test_outside_changes_are_rejected_independently_of_domain_metadata(self):
        try:
            import cv2
            import numpy as np
        except ImportError:
            self.skipTest("Run pixel tests in the dedicated special runtime.")
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            original = np.zeros((12, 12, 3), dtype=np.uint8)
            mask = np.zeros((12, 12), dtype=np.uint8)
            mask[4:8, 4:8] = 255
            output = original.copy()
            output[5, 5] = 128
            source, result = root / "source.png", root / "result.png"
            cv2.imwrite(str(source), original)
            cv2.imwrite(str(root / "mask.png"), mask)
            cv2.imwrite(str(result), output)
            metadata = {"artifacts": {"authorized_mask": "mask.png"}}
            report = verify(source, result, root, metadata)
            self.assertEqual(report["changed_pixels"], 1)
            self.assertEqual(report["changed_outside_mask"], 0)
            output[0, 0] = 255
            cv2.imwrite(str(result), output)
            with self.assertRaisesRegex(ValueError, "fora da máscara"):
                verify(source, result, root, metadata)


if __name__ == "__main__":
    unittest.main()
