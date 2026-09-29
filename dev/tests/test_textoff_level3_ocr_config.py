import unittest

from processamento.limpeza_baloes.level3_regional.ocr_config import (
    OCR_LANGUAGE_GROUPS,
    create_readers,
    manifest_metadata,
)


class TextOffRegionalOcrConfigTests(unittest.TestCase):
    def test_creates_supported_reader_groups(self):
        calls = []

        def reader_factory(languages, gpu):
            calls.append((languages, gpu))
            return object()

        readers = create_readers(reader_factory)

        self.assertEqual(tuple(group for group, _ in readers), OCR_LANGUAGE_GROUPS)
        self.assertEqual(calls, [
            (["en", "ko"], False),
            (["ch_sim", "en"], False),
            (["ch_tra", "en"], False),
        ])

    def test_manifest_records_configured_groups_and_reader_usage(self):
        metadata = manifest_metadata([{
            "detections": [
                {"reader_languages": ["en", "ko"]},
                {"reader_languages": ["ch_sim", "en"]},
            ],
        }])

        self.assertEqual(metadata["configured_languages"], ["ch_sim", "ch_tra", "en", "ko"])
        self.assertEqual(metadata["detection_count"], 2)
        self.assertEqual(metadata["detection_count_by_reader"], {
            "en+ko": 1, "ch_sim+en": 1, "ch_tra+en": 0,
        })
        self.assertIn("não identifica", metadata["language_semantics"])


if __name__ == "__main__":
    unittest.main()
