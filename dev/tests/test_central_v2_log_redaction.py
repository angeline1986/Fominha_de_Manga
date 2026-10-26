"""Personal filesystem paths stay out of Central V2 terminal and worker logs."""
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from central_v2.backend.log_redaction import redact_log_text
from central_v2.backend.redacted_subprocess import launch
from orquestracao.central_session import central_session, run_central


PRIVATE = "/Users/example/Documents/TI/Projetos/Fominha_de_Manga"


class LogRedactionTests(unittest.TestCase):
    def test_warning_and_traceback_paths_are_redacted(self):
        source = (f'{PRIVATE}/.venv/lib/torch.py:176: FutureWarning\n'
                  f'  File "{PRIVATE}/worker.py", line 12, in main\n')
        result = redact_log_text(source)
        self.assertNotIn("/Users/example", result)
        self.assertIn("[HOME]/Documents/TI/Projetos", result)
        self.assertIn("FutureWarning", result)
        self.assertIn("worker.py", result)

    def test_project_runtime_path_is_replaced_as_a_whole(self):
        root = Path(__file__).resolve().parents[2]
        result = redact_log_text(f"{root}/central_v2/runtime/textoff/merged_nivel_ii/.venv/lib/torch.py")
        self.assertEqual(result, "[PROJETO]/central_v2/runtime/textoff/merged_nivel_ii/.venv/lib/torch.py")

    def test_worker_stdout_and_stderr_are_redacted_before_writing(self):
        output = io.StringIO()
        code = (f'import sys; print("output={PRIVATE}/page.png"); '
                f'print("warning={PRIVATE}/torch.py:176", file=sys.stderr)')
        process, reader = launch([sys.executable, "-c", code], cwd=Path.cwd(),
                                 destination=output)
        self.assertEqual(process.wait(timeout=5), 0)
        reader.join(timeout=5)
        self.assertFalse(reader.is_alive())
        self.assertNotIn(PRIVATE, output.getvalue())
        self.assertIn("[HOME]/Documents/TI/Projetos", output.getvalue())

    def test_menu_redacts_direct_and_inherited_child_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            lock = Path(temporary) / "central.lock"
            output = io.StringIO()
            code = (f'import subprocess,sys; print("server={PRIVATE}/server.py"); '
                    f'subprocess.run([sys.executable,"-c",'
                    f'"import sys; print(\\\"worker={PRIVATE}/torch.py\\\",file=sys.stderr)"])')
            with patch("orquestracao.central_session.LOCK_PATH", lock), \
                 patch("orquestracao.central_session.sys.stdout", output):
                run_central([sys.executable, "-c", code], Path.cwd())
            self.assertNotIn(PRIVATE, output.getvalue())
            self.assertIn("[HOME]/Documents/TI/Projetos", output.getvalue())
            self.assertIn("server=", output.getvalue())
            self.assertIn("worker=", output.getvalue())
            with central_session(lock):
                pass
