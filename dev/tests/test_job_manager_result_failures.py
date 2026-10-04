import unittest

from central_v2.backend.jobs import manager


class JobManagerResultFailureTests(unittest.TestCase):
    def _job(self, job_id):
        return {
            "id": job_id, "status": "queued", "chapter": "",
            "progress": {"percent": 0, "message": "queued"},
            "results": [], "error": "", "created_at": "", "updated_at": "",
        }

    def test_chapter_failure_marks_job_failed_and_preserves_result(self):
        job_id = "failure-contract-test"
        with manager._lock:
            manager._jobs[job_id] = self._job(job_id)
        self.addCleanup(lambda: manager._jobs.pop(job_id, None))

        results = [{"chapter": "1", "status": "failed", "error": "stage inválido"}]
        manager._run(job_id, lambda _progress, _id: results)

        job = manager.get_job(job_id)
        self.assertEqual(job["status"], "failed")
        self.assertIn("1 de 1 capítulo(s) falharam", job["error"])
        self.assertIn("stage inválido", job["error"])
        self.assertEqual(job["results"], results)

    def test_no_change_result_remains_completed(self):
        job_id = "no-change-contract-test"
        with manager._lock:
            manager._jobs[job_id] = self._job(job_id)
        self.addCleanup(lambda: manager._jobs.pop(job_id, None))

        results = [{"chapter": "1", "status": "no_change"}]
        manager._run(job_id, lambda _progress, _id: results)

        self.assertEqual(manager.get_job(job_id)["status"], "completed")


if __name__ == "__main__":
    unittest.main()
