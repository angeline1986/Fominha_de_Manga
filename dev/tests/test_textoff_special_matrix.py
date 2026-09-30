"""Identically named pages in different chapters must all be processed."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from central_v2.backend.orchestration.textoff_special.artifacts import sha256, write_json

SCRIPT = Path(__file__).resolve().parents[1] / "tools/textoff_special_matrix.py"
SPEC = importlib.util.spec_from_file_location("special_matrix", SCRIPT)
matrix = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(matrix)


class MatrixChapterTests(unittest.TestCase):
    def test_resume_does_not_skip_same_filename_in_another_chapter(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            inputs = []
            for chapter in ("1", "3"):
                image = root / chapter / "page.png"
                image.parent.mkdir()
                image.write_bytes(chapter.encode())
                inputs.append({"chapter": chapter, "filename": "page.png", "level": "MERGED_NIVEL_I",
                               "sha256": sha256(image), "path_relative_to_work": str(image.relative_to(root)),
                               "selections": [{"x": 0, "y": 0, "width": 5, "height": 5}]})
            inventory, report = root / "inventory.json", root / "matrix.json"
            write_json(inventory, {"roi_status": "fixed_for_comparison", "local_work_root": str(root),
                                   "inputs": inputs})
            initial = [{"chapter": "1", "filename": "page.png", "level": "MERGED_NIVEL_I", "treatment": key}
                       for key in ("transparente", "transparente_legacy")]
            write_json(report, {"inventory_sha256": sha256(inventory), "runs": initial})

            def preview(_root, payload):
                return {"run_id": "fixture", "execution_status": "failed", "duration_seconds": 0,
                        "error": {"error": "No components"}}

            with patch.object(matrix, "preview", side_effect=preview) as runner:
                result = matrix.execute(inventory, report)
            self.assertEqual(len(result["runs"]), 4)
            self.assertEqual(runner.call_count, 2)
            self.assertTrue(all(call.args[1]["chapter"] == "3" for call in runner.call_args_list))
            self.assertTrue(result["inputs_unchanged"])


if __name__ == "__main__":
    unittest.main()
