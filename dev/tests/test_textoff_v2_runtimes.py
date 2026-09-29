import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from central_v2.backend.orchestration.textoff_merged import cleaner_process, runtime


class TextoffV2RuntimeTests(unittest.TestCase):
    def test_runtime_resolves_each_feature_under_central_v2(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for feature in ("merged_nivel_i", "merged_nivel_ii"):
                interpreter = root / feature / ".venv" / "bin" / "python"
                interpreter.parent.mkdir(parents=True)
                interpreter.touch()
            with patch.object(runtime, "TEXT_OFF_RUNTIME_ROOT", root):
                self.assertEqual(runtime.python_for("merged_nivel_i"),
                                 root / "merged_nivel_i" / ".venv" / "bin" / "python")
                self.assertEqual(runtime.python_for("merged_nivel_ii"),
                                 root / "merged_nivel_ii" / ".venv" / "bin" / "python")

    def test_panel_cleaner_command_uses_the_merged_level1_runtime(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            python, source, output, progress = (root / name for name in ("python", "in", "out", "progress.json"))
            with patch.object(cleaner_process, "python_for", return_value=python):
                command = cleaner_process.panel_cleaner_command(source, output, progress)
            self.assertEqual(command[0], str(python))
            self.assertEqual(command[2:6], ["-i", str(source.resolve()), "-o", str(output.resolve())])
            self.assertIn("--offline", command)

    def test_missing_or_invalid_runtime_is_reported(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(runtime, "TEXT_OFF_RUNTIME_ROOT", Path(folder)):
                with self.assertRaisesRegex(RuntimeError, "Ambiente da Central V2"):
                    runtime.python_for("merged_nivel_i")
                with self.assertRaisesRegex(ValueError, "Nome de runtime"):
                    runtime.python_for("../outside")


if __name__ == "__main__":
    unittest.main()
