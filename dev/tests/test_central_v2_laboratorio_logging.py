"""Structured lifecycle logs for the Laboratory preview routes."""
import unittest
from unittest.mock import patch

from central_v2.backend.routes import laboratorio_logging


class LaboratoryLoggingTests(unittest.TestCase):
    def setUp(self):
        self.events = []
        self.patch_emit = patch.object(
            laboratorio_logging, "emit",
            side_effect=lambda *args, **kwargs: self.events.append((args, kwargs)))
        self.patch_emit.start()
        self.addCleanup(self.patch_emit.stop)

    def test_success_logs_start_execution_and_real_run_identifier(self):
        result = laboratorio_logging.run_treatment_logged(
            "estilizado", {"chapter": "19", "page": "page-001.png"},
            lambda: {"execution_status": "succeeded", "run_id": "a" * 32})
        self.assertEqual(result["execution_status"], "succeeded")
        self.assertEqual([event[0][1] for event in self.events], [
            "tratamento iniciado", "tratamento em execução", "tratamento concluído"])
        start, finish = self.events[0][1], self.events[-1][1]
        self.assertEqual(start["job_id"], finish["job_id"])
        self.assertEqual(finish["run_id"], "a" * 32)
        self.assertEqual(start["página"], "page-001.png")

    def test_expected_degrade_review_is_not_logged_as_processing_failure(self):
        laboratorio_logging.run_treatment_logged(
            "degrade", {"chapter": "19", "page": "page-001.png"},
            lambda: {"execution_status": "failed", "run_id": "b" * 32,
                     "error": {"error": "Nenhum componente autorizado intersecta as seleções."}})
        self.assertEqual(self.events[-1][0][1],
                         "classificação aguardando autorização explícita")
        self.assertEqual(self.events[-1][0][0], "INFO")

    def test_worker_exception_is_logged_and_rethrown(self):
        def fail():
            raise RuntimeError("worker falhou")
        with self.assertRaisesRegex(RuntimeError, "worker falhou"):
            laboratorio_logging.run_treatment_logged(
                "gradiente_suave", {"chapter": "19", "page": "page-001.png"}, fail)
        self.assertEqual(self.events[-1][0][:2], ("ERROR", "tratamento falhou"))
        self.assertEqual(self.events[-1][1]["detalhe"], "RuntimeError")


if __name__ == "__main__":
    unittest.main()
