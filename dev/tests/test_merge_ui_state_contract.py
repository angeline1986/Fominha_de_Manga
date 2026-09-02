import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "interface_web" / "app.js"


class MergeUiStateContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.js = APP.read_text(encoding="utf-8")

    def test_level2_list_requires_partial_not_yet_validated(self):
        """
        Um estado parcial já validado pelo Level II não pode voltar
        para a fila executável do Auto-Merge Nível II.
        """
        self.assertRegex(
            self.js,
            re.compile(
                r"function\s+level2Chapters\s*\(\)\s*\{"
                r"[^}]*merge_state\s*===\s*[\"']parcial[\"']"
                r"[^}]*!\s*x\.merge_level2_validated",
                re.S,
            ),
        )

    def test_overview_partial_action_respects_level2_validation(self):
        """
        A Visão Geral não pode oferecer goLevel2 para um parcial
        cujo Level II já foi validado.
        """
        self.assertIn(
            "merge_level2_validated",
            self._overview_source(),
        )

    def test_review_list_does_not_accept_partial_state(self):
        """
        Review continua sendo destino apenas de pendente_review
        ou de capítulo que já possua proposta de Review.
        """
        match = re.search(
            r"function\s+review\s*\([^)]*\)\s*\{(.{0,500})",
            self.js,
            re.S,
        )
        self.assertIsNotNone(match)

        source = match.group(1)

        self.assertIn('merge_state==="pendente_review"', source)
        self.assertNotIn('merge_state==="parcial"', source)

    def test_merge_error_does_not_directly_mark_review_attention(self):
        """
        Falha/misto no Auto-Merge não significa automaticamente
        que o capítulo já está pronto para Review.
        """
        self.assertNotRegex(
            self.js,
            re.compile(
                r'page\s*===\s*[\"\']merge[\"\']'
                r'.{0,500}'
                r'data-page=[\"\']review[\"\']',
                re.S,
            ),
        )

    def test_level2_modal_distinguishes_zero_pending(self):
        """
        O modal do Level II precisa distinguir capítulos que ainda
        possuem pending daqueles concluídos/promovidos sem Review.
        """
        match = re.search(
            r"function\s+level2ResultModal\s*\([^)]*\)\s*\{(.+?)"
            r"\n\}",
            self.js,
            re.S,
        )
        self.assertIsNotNone(match)

        source = match.group(1)

        self.assertRegex(
            source,
            re.compile(
                r"pending\s*(?:===|>|[?])",
                re.S,
            ),
        )

    def _overview_source(self):
        start = self.js.find("function overview(")
        self.assertNotEqual(start, -1)

        end = self.js.find("function mergeLabel(", start)
        self.assertNotEqual(end, -1)

        return self.js[start:end]


if __name__ == "__main__":
    unittest.main()
