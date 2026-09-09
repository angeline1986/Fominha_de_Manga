from pathlib import Path
import unittest


class RidiProcessingProviderContractTest(unittest.TestCase):
    def test_processing_web_accepts_and_catalogs_ridi(self):
        root = Path(__file__).resolve().parents[2]
        source = (root / "interface_web" / "processing_web.py").read_text(encoding="utf-8")

        self.assertIn(
            'if provider not in {"comix","mangago","ridi"}: raise ValueError("Provider inválido.")',
            source,
        )
        self.assertIn(
            'for provider in ("comix","mangago","ridi"):',
            source,
        )
        self.assertNotIn(
            'if provider not in {"comix","mangago"}: raise ValueError("Provider inválido.")',
            source,
        )
        self.assertNotIn(
            'for provider in ("comix","mangago"):',
            source,
        )


if __name__ == "__main__":
    unittest.main()
