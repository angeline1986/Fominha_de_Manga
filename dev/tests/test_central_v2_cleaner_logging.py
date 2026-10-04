import json
import queue
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from central_v2.backend.orchestration.textoff_merged import cleaner_logging, cleaner_process
from processamento.limpeza_baloes.cleaner_v2 import main as cleaner_main
from processamento.limpeza_baloes.cleaner_v2 import launcher


class CleanerLoggingTests(unittest.TestCase):
    def test_central_command_uses_structured_mode(self):
        command = cleaner_process.panel_cleaner_command(
            Path("/input"), Path("/output"), Path("/progress.json"), "cap-1")
        self.assertIn("--central-mode", command)

    def test_tqdm_parser_and_progress_file_contract_remain_available(self):
        self.assertEqual(cleaner_main._stage_from_line("Running text detection AI model", "preparacao"),
                         "deteccao")
        self.assertEqual(cleaner_main.PROGRESS_RE.search("50%|████ 5/10").groups(), ("50", "5", "10"))

    def test_tqdm_fragment_attached_to_warning_is_removed_only_from_central_diagnostic(self):
        raw = ("4%|▎ | 2/57 [00:12<04:48, 5.24s/it]"
               "2026-10-04 16:55:54.427 | WARNING | pcleaner.image_ops:pick_best_mask:618 - "
               "Found an empty mask, the Text Detector didn't find anything but still recorded text present.")
        progress_match = cleaner_main.PROGRESS_RE.search(raw)
        self.assertEqual(progress_match.groups(), ("4", "2", "57"))
        self.assertEqual(cleaner_main._log_level(raw), "WARNING")

        message = cleaner_main._central_diagnostic_message(raw)
        self.assertIn("WARNING | pcleaner.image_ops:pick_best_mask:618", message)
        self.assertIn("Found an empty mask", message)
        for fragment in ("4%|", "2/57", "00:12<04:48", "5.24s/it"):
            self.assertNotIn(fragment, message)

        messages = queue.Queue()
        messages.put(("stdout", json.dumps({"type": "central_log", "event": "diagnostic",
                                              "level": "WARNING", "message": message})))
        with patch.object(cleaner_logging, "emit") as log:
            cleaner_logging.consume_messages(messages, [], [])
        self.assertEqual(log.call_args.args[0:2], ("WARNING", "diagnóstico do Cleaner"))
        logged_detail = log.call_args.kwargs["detalhe"]
        self.assertIn("Found an empty mask", logged_detail)
        self.assertNotIn("4%|", logged_detail)

    def test_standalone_launcher_does_not_enable_central_mode(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, destination = root / "source", root / "destination"
            source.mkdir()
            command = launcher.build_command(source, destination, offline=True)
        self.assertIn("--offline", command)
        self.assertNotIn("--central-mode", command)

    def test_cleaner_main_progress_is_reserved_below_completion(self):
        class Job:
            progress_value = 0
            progress_detail = ""
            message = ""

        job = Job()
        with tempfile.TemporaryDirectory() as temporary:
            progress_file = Path(temporary) / "progress.json"
            progress_file.write_text(json.dumps({"overall": 1.0, "updated_at": 7,
                                                 "detail": "Cleaner V2 concluído"}), encoding="utf-8")
            cleaner_process._report_progress(progress_file, job, "3", None)
        self.assertEqual(job.progress_value, cleaner_process.PANEL_CLEANER_PROGRESS_MAX)
        self.assertEqual(job.progress_detail, "Cap. 3: Cleaner V2 concluído")

    def test_central_events_use_a_separate_json_stdout_protocol(self):
        with patch("builtins.print") as output:
            cleaner_main._central_event("stage_completed", stage="deteccao", duration_seconds=1.2)
        event = json.loads(output.call_args.args[0])
        self.assertEqual(event, {"type": "central_log", "event": "stage_completed",
                                 "stage": "deteccao", "duration_seconds": 1.2})
        self.assertEqual(cleaner_main._log_level("[WARNING] OCR fallback"), "WARNING")
        self.assertEqual(cleaner_main._log_level("[DEBUG] detalhe"), None)

    def test_warning_and_error_diagnostics_are_forwarded(self):
        messages = queue.Queue()
        messages.put(("stdout", json.dumps({"type": "central_log", "event": "diagnostic",
                                             "level": "WARNING", "message": "aviso"})))
        messages.put(("stderr", "falha externa"))
        stdout_tail, stderr_tail = [], []
        with patch.object(cleaner_logging, "emit") as log:
            cleaner_logging.consume_messages(messages, stdout_tail, stderr_tail)
        self.assertEqual(stdout_tail[0].find("central_log") >= 0, True)
        self.assertEqual(stderr_tail, ["falha externa"])
        self.assertEqual([call.args[0] for call in log.call_args_list], ["WARNING", "WARNING"])


if __name__ == "__main__":
    unittest.main()
