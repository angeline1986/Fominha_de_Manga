"""Contrato de escrita do Auto-Cleaner no diretório numerado."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from central_v2.backend.orchestration.textoff_merged import execution
from central_v2.backend.orchestration.textoff_merged.stages import LEVEL1


class NumberedLevel1OutputTests(TestCase):
    def test_level1_writes_directly_to_numbered_folder(self):
        with TemporaryDirectory() as temporary:
            manga = Path(temporary) / "manga"
            chapter = manga / "IMG" / "1"
            chapter.mkdir(parents=True)

            output_dirs = []

            def fake_cleaner(images, output_dir, **kwargs):
                output_dirs.append(Path(output_dir))
                return {"status": "ok"}

            with (
                patch.object(execution, "validate_selection"),
                patch.object(execution.v3, "is_chapter_merged", return_value=True),
                patch.object(
                    execution.v3,
                    "merge_artifact_files",
                    return_value=[chapter / "page.png"],
                ),
                patch.object(execution.v3, "merge_output_dir", return_value=chapter),
                patch.object(execution, "run_cleaner_v2", side_effect=fake_cleaner),
                patch.dict("os.environ", {"CENTRAL_V2_LEVEL1_NUMBERED": "1"}),
                patch.object(execution, "mirror_stage_chapter") as mirror,
            ):
                result = execution.execute_merged(
                    manga,
                    ["1"],
                    lambda chapter, event: None,
                    output_stage=LEVEL1,
                    include_legacy_level2=False,
                )

            expected = (
                manga / "FLUXO_SECUNDARIO" / "04_TEXTO_OFF"
                / "01_AUTO_CLEANER" / "1"
            )

            self.assertEqual(result[0]["status"], "ok")
            self.assertEqual(output_dirs, [expected])
            mirror.assert_not_called()


if __name__ == "__main__":
    import unittest
    unittest.main()
