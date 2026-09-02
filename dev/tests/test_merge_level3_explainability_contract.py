import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

class MergeLevel3ExplainabilityContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = (ROOT / "interface_web" / "app.js").read_text(encoding="utf-8")
        cls.backend = (ROOT / "interface_web" / "processing_web.py").read_text(encoding="utf-8")

    def test_ui_semantics(self):
        self.assertIn("✓ Analisado", self.app)
        self.assertIn("Analisar Nível III", self.app)
        self.assertIn("Aguardando análise estrutural", self.app)

    def test_ui_distinguishes_outcomes(self):
        self.assertIn("Parcialmente resolvido", self.app)
        self.assertIn("Não resolvido", self.app)
        self.assertIn("Resolvido automaticamente", self.app)

    def test_ui_exposes_diagnostics(self):
        self.assertIn("CANDIDATOS AVALIADOS", self.app)
        self.assertIn("stats.decisions.UNSAFE", self.app)
        self.assertIn("stats.decisions.INCONCLUSIVE", self.app)
        self.assertIn("Principais motivos encontrados na busca local", self.app)

    def test_backend_feedback(self):
        self.assertIn("nenhum trecho pôde ser comprovado como SAFE", self.backend)
        self.assertIn("região(ões) SAFE", self.backend)
        self.assertIn("analisado e resolvido automaticamente", self.backend)

if __name__ == "__main__":
    unittest.main()
