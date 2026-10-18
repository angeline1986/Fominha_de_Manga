"""Testes do extrator de balões transparentes."""
import copy
import json
import unittest
from pathlib import Path

from config.data_paths import OUTPUT_ROOT
from central_v2.backend.orchestration.textoff_merged.transparent_candidates import (
    extract_candidates,
)


REPORT = (
    Path(OUTPUT_ROOT)
    / "comix/Gazing at you/FLUXO_SECUNDARIO/04_TEXTO_OFF"
    / "TO_MERGED_NIVEL_I/12/json/level1-balloon-report.json"
)


class TransparentCandidatesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = json.loads(REPORT.read_text(encoding="utf-8"))

    def test_real_chapter(self):
        rows = extract_candidates(self.report)
        self.assertEqual(len(rows), 25)
        self.assertEqual(len({r["source"] for r in rows}), 12)
        self.assertEqual(len({r["id"] for r in rows}), 25)

    def test_deterministic_ids(self):
        first = extract_candidates(self.report)
        second = extract_candidates(self.report)
        self.assertEqual(first, second)

    def test_rejects_unknown_algorithm(self):
        report = copy.deepcopy(self.report)
        report["algorithm"] = "unknown"
        with self.assertRaises(ValueError):
            extract_candidates(report)

    def test_rejects_invalid_geometry(self):
        report = copy.deepcopy(self.report)
        page = next(p for p in report["pages"]
                    if p.get("transparent_balloons"))
        page["transparent_balloons"][0]["bbox"] = [1, 2, -3, 4]
        with self.assertRaises(ValueError):
            extract_candidates(report)

    def test_rejects_duplicate_balloon(self):
        report = copy.deepcopy(self.report)
        page = next(p for p in report["pages"]
                    if p.get("transparent_balloons"))
        page["transparent_balloons"].append(
            copy.deepcopy(page["transparent_balloons"][0])
        )
        with self.assertRaises(ValueError):
            extract_candidates(report)


if __name__ == "__main__":
    unittest.main()
