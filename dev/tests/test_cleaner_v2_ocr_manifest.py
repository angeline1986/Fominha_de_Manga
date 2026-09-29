import unittest
from pathlib import Path

from processamento.limpeza_baloes.cleaner_v2.integration import MODULE_DIR, PROFILE_NAME
from processamento.limpeza_baloes.cleaner_v2.ocr_manifest import ocr_manifest_metadata


class CleanerV2OcrManifestTests(unittest.TestCase):
    def test_manifest_reports_effective_language_and_profile_limitations(self):
        metadata = ocr_manifest_metadata(MODULE_DIR / PROFILE_NAME)
        self.assertTrue(metadata["enabled"])
        self.assertEqual(metadata["configured_language"], "detect_box")
        self.assertEqual(metadata["configured_engine"], "auto")
        self.assertEqual(metadata["effective_engine"], "MangaOCR")
        self.assertEqual(metadata["effective_language"], "jpn")
        self.assertIn("Korean and Chinese OCR are not enabled", metadata["note"])


if __name__ == "__main__":
    unittest.main()
