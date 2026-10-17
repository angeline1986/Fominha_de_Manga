import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from central_v2.backend.orchestration.combo_turbo.validation import validate_chapter
from central_v2.backend.orchestration.combo_turbo import validation


class ComboValidationSummaryTests(unittest.TestCase):
    def test_page_validation_is_debug_only_and_preserves_diagnostic_fields(self):
        item = {"status": "UNVERIFIED", "reasons": ["CHECK_MANIFEST_MISSING"],
                "integrity_ok": False, "check_verified": False,
                "artifact_sha256": None, "mask_sha256": None, "manifest_sha256": "abc"}
        with (patch.object(validation, "validate_solids_page", return_value=item),
              patch("central_v2.backend.operational_log._MIN_LEVEL", 20),
              contextlib.redirect_stdout(io.StringIO()) as output):
            result = validation.validate_page(Path("/tmp/manga"), "comix", "12",
                                              "page.png", "SOLIDOS")
        self.assertEqual(result, item)
        self.assertEqual(output.getvalue(), "")
        with (patch.object(validation, "validate_solids_page", return_value=item),
              patch("central_v2.backend.operational_log._MIN_LEVEL", 10),
              contextlib.redirect_stdout(io.StringIO()) as output):
            validation.validate_page(Path("/tmp/manga"), "comix", "12",
                                     "page.png", "SOLIDOS")
        self.assertEqual(output.getvalue().count("DEBUG"), 2)
        self.assertIn("CHECK_MANIFEST_MISSING", output.getvalue())

    def test_partial_chapter_summary_is_page_scoped_and_deterministic(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pages = [root / "page-1.png", root / "page-2.png"]
            statuses = {
                ("SOLIDOS", pages[0].name): "MISSING",
                ("GLASS", pages[0].name): "MISSING",
                ("SOLIDOS", pages[1].name): "REUSABLE",
                ("GLASS", pages[1].name): "UNVERIFIED",
            }

            def fake_validate(_manga, _provider, _chapter, page, stage):
                status = statuses[(stage, page)]
                return {"stage": stage, "chapter": "12", "page": page,
                        "status": status, "reasons": []}

            with (patch("central_v2.backend.orchestration.combo_turbo.validation.v3.merge_output_dir",
                        return_value=root / "merge"),
                  patch("central_v2.backend.orchestration.combo_turbo.validation.v3.merge_artifact_files",
                        return_value=pages),
                  patch("central_v2.backend.orchestration.combo_turbo.validation.stage_chapter",
                        side_effect=FileNotFoundError),
                  patch("central_v2.backend.orchestration.combo_turbo.validation.validate_page",
                        side_effect=fake_validate),
                  contextlib.redirect_stdout(io.StringIO())):
                first = validate_chapter(root, "comix", "12")
                second = validate_chapter(root, "comix", "12")

            self.assertEqual(first, second)
            self.assertEqual(first["pages_analyzed"], 2)
            self.assertEqual(first["without_artifact"], 1)
            self.assertEqual(first["solids"]["REUSABLE"], 1)
            self.assertEqual(first["glass"]["UNVERIFIED"], 1)
            self.assertEqual(first["unverified"], 1)


if __name__ == "__main__":
    unittest.main()
