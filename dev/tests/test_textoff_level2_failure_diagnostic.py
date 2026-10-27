"""Keep the failing page visible from the Level II worker through the job result."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from central_v2.backend.jobs import manager
from central_v2.backend.orchestration.textoff_merged import level2, level2_batch
from central_v2.backend.orchestration.textoff_merged.level2_failure import failure_message


PAGE = "page-053-062.png"
REASON = f"Rótulo 1 sem pixels para balão em {PAGE}; reexecute o Nível I."


class Level2FailureDiagnosticTests(unittest.TestCase):
    def test_batch_records_chapter_and_page_without_hiding_original_error(self):
        with tempfile.TemporaryDirectory() as root:
            progress_path = Path(root) / "progress.json"
            job = {"chapter": "22", "source_dir": root, "level1_dir": root,
                   "output_dir": root, "report": str(Path(root) / "report.json"),
                   "candidate_pages": [PAGE]}
            with patch.object(level2_batch, "process", side_effect=ValueError(REASON)):
                with self.assertRaisesRegex(ValueError, PAGE):
                    level2_batch.process_batch([job], progress_path)
            payload = json.loads(progress_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "failed")
            self.assertEqual(payload["chapter"], "22")
            self.assertEqual(payload["page"], PAGE)
            self.assertEqual(payload["error"], REASON)

    def test_worker_error_reaches_result_and_progress_log(self):
        with tempfile.TemporaryDirectory() as root:
            manga = Path(root) / "manga"
            target = Path(root) / "level2" / "22"
            source = Path(root) / "merge"
            level1 = Path(root) / "level1"
            messages = []

            class FailedProcess:
                returncode = 1

                def poll(self):
                    return 1

            class Reader:
                def join(self, timeout=None):
                    pass

            def launch(command, **_kwargs):
                progress = Path(command[command.index("--progress") + 1])
                progress.write_text(json.dumps({"status": "failed", "chapter": "22",
                                                "page": PAGE, "error": REASON}), encoding="utf-8")
                return FailedProcess(), Reader()

            with patch.object(level2, "validate_level2_selection"), \
                 patch.object(level2, "python_for", return_value="/fake/python"), \
                 patch.object(level2.v3, "is_chapter_merged", return_value=True), \
                 patch.object(level2.v3, "merge_output_dir", return_value=source), \
                 patch.object(level2, "query_merged_level2", return_value={"chapters": [
                     {"chapter": "22", "level2_candidate_pages": [PAGE]}]}), \
                 patch.object(level2, "isolated_level2_target", return_value=None), \
                 patch.object(level2, "stage_chapter", side_effect=lambda _m, stage, _c,
                              read_legacy=True: level1 if stage == level2.LEVEL1 else target), \
                 patch.object(level2, "load_level1_protection_context", return_value=({}, None)), \
                 patch.object(level2, "capture_reset_bases", return_value={}), \
                 patch.object(level2, "launch", side_effect=launch):
                results = level2.execute_merged_level2(
                    manga, ["22"], lambda _chapter, progress: messages.append(progress["message"]),
                    provider="comix", manga_name="work")
            self.assertEqual(results[0]["status"], "failed")
            self.assertIn("Cap. 22", results[0]["error"])
            self.assertIn(PAGE, results[0]["error"])
            self.assertTrue(any(PAGE in message for message in messages))

    def test_missing_or_invalid_worker_diagnostic_preserves_fallback(self):
        with tempfile.TemporaryDirectory() as root:
            progress = Path(root) / "progress.json"
            fallback = "Nível II encerrou sem resultado validado (código 1)."
            self.assertEqual(failure_message(progress, 1, ["22"]), fallback)
            progress.write_text(json.dumps({"status": "failed", "chapter": "23",
                                            "page": PAGE, "error": REASON}), encoding="utf-8")
            self.assertEqual(failure_message(progress, 1, ["22"]), fallback)

    def test_job_error_and_terminal_log_include_page_for_popup(self):
        job_id = "a" * 32
        job = {"id": job_id, "status": "queued", "progress": {"total": 1},
               "results": [], "error": "", "updated_at": ""}
        result = {"chapter": "22", "status": "failed", "error": f"Cap. 22: {REASON}"}
        with patch.dict(manager._jobs, {job_id: job}), patch.object(manager, "emit") as emit:
            manager._run(job_id, lambda _update, _job_id: [result])
            self.assertIn(PAGE, manager.get_job(job_id)["error"])
            self.assertTrue(any(PAGE in str(call) for call in emit.call_args_list))


if __name__ == "__main__":
    unittest.main()
