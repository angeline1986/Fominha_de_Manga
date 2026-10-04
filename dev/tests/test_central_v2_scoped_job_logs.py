import unittest
import threading
from unittest.mock import patch

from central_v2.backend.jobs import manager


class ScopedJobLogTests(unittest.TestCase):
    def test_cleaner_job_stays_below_100_during_authorization_then_completes_atomically(self):
        job_id = "cleaner-progress-contract"
        authorization_started = threading.Event()
        finish_authorization = threading.Event()
        manager._jobs[job_id] = {
            "id": job_id, "status": "queued", "chapter": "", "progress": {"percent": 0},
            "results": [], "error": "", "created_at": manager._now(),
            "updated_at": manager._now(),
        }

        def operation(progress, _job_id):
            progress("3", {"stage": "clean", "percent": 90, "message": "Cleaner V2 concluído"})
            progress("3", {"stage": "done", "percent": 100, "message": "Cleaner concluído"})
            authorization_started.set()
            if not finish_authorization.wait(timeout=5):
                raise TimeoutError("authorization test gate timed out")
            return [{"chapter": "3", "status": "ok"}]

        thread = threading.Thread(target=manager._run, args=(job_id, operation, "CLEANER-I"))
        try:
            with patch("central_v2.backend.jobs.manager.emit"):
                thread.start()
                self.assertTrue(authorization_started.wait(timeout=5))
                during_authorization = manager.get_job(job_id)
                self.assertEqual(during_authorization["status"], "running")
                self.assertLess(during_authorization["progress"]["percent"], 100)
                self.assertEqual(during_authorization["progress"]["percent"], 99)
                finish_authorization.set()
                thread.join(timeout=5)
            self.assertFalse(thread.is_alive())
            completed = manager.get_job(job_id)
            self.assertEqual(completed["status"], "completed")
            self.assertEqual(completed["progress"]["percent"], 100)
        finally:
            finish_authorization.set()
            if thread.is_alive():
                thread.join(timeout=5)
            manager._jobs.pop(job_id, None)

    def test_failed_cleaner_job_does_not_finish_at_100_percent(self):
        job_id = "cleaner-failed-progress-contract"
        manager._jobs[job_id] = {
            "id": job_id, "status": "queued", "chapter": "", "progress": {"percent": 0},
            "results": [], "error": "", "created_at": manager._now(),
            "updated_at": manager._now(),
        }

        def operation(progress, _job_id):
            progress("3", {"stage": "done", "percent": 100, "message": "Cleaner concluído"})
            return [{"chapter": "3", "status": "failed", "error": "consolidação falhou"}]

        try:
            with patch("central_v2.backend.jobs.manager.emit"):
                manager._run(job_id, operation, "CLEANER-I")
            failed = manager.get_job(job_id)
            self.assertEqual(failed["status"], "failed")
            self.assertLess(failed["progress"]["percent"], 100)
        finally:
            manager._jobs.pop(job_id, None)

    def test_sommelier_logs_completed_page_once_and_preserves_structured_progress(self):
        job_id = "a1b2c3d4" + "0" * 24
        manager._jobs[job_id] = {
            "id": job_id, "status": "queued", "chapter": "", "progress": {},
            "results": [], "error": "", "created_at": manager._now(),
            "updated_at": manager._now(),
        }

        def operation(progress, _job_id):
            progress("1", {"stage": "run_started", "percent": 0, "completed": 0,
                            "total": 1, "message": "start"})
            progress("1", {"stage": "page_started", "page_index": 1, "percent": 0,
                            "completed": 0, "total": 1, "message": "inferindo"})
            progress("1", {"stage": "page", "page_index": 1, "percent": 100,
                            "completed": 1, "total": 1, "duration": 2.5,
                            "bubbles": 3, "candidates": 1, "message": "concluída"})
            progress("1", {"stage": "completed", "percent": 100, "completed": 1,
                            "total": 1, "pages": 1, "bubbles": 3,
                            "candidates": 1, "duration": 2.6, "message": "fim"})
            return [{"chapter": "1", "status": "ok", "pages": 1,
                     "balloons": 3, "candidates": 1}]

        try:
            with patch("builtins.print") as output:
                manager._run(job_id, operation, "SOMMELIER")
            lines = [call.args[0] for call in output.call_args_list]
            pages = [line for line in lines if "página concluída" in line]
            self.assertEqual(len(pages), 1)
            self.assertIn("página=1/1", pages[0])
            self.assertIn("duração=2.5s", pages[0])
            self.assertFalse(any("inferindo" in line or "100%" in line for line in lines))
            self.assertEqual(manager.get_job(job_id)["progress"]["percent"], 100)
            self.assertTrue(any("execução concluída" in line for line in lines))
        finally:
            manager._jobs.pop(job_id, None)

    def test_operation_exception_is_logged_as_error_with_job_identity(self):
        job_id = "deadbeef" + "0" * 24
        manager._jobs[job_id] = {
            "id": job_id, "status": "queued", "chapter": "", "progress": {},
            "results": [], "error": "", "created_at": manager._now(),
            "updated_at": manager._now(),
        }
        try:
            with patch("builtins.print") as output:
                manager._run(job_id, lambda *_args: (_ for _ in ()).throw(
                    RuntimeError("Node stderr cause")), "SOMMELIER")
            lines = [call.args[0] for call in output.call_args_list]
            errors = [line for line in lines if " ERROR " in line]
            self.assertTrue(errors)
            self.assertTrue(all("[SOMMELIER][deadbe" in line for line in errors))
            self.assertTrue(any("Node stderr cause" in line for line in errors))
        finally:
            manager._jobs.pop(job_id, None)


if __name__ == "__main__":
    unittest.main()
