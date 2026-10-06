import json
import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import patch

from central_v2.backend.orchestration.bubble_sommelier import execution
from central_v2.backend.orchestration.bubble_sommelier.mapear_results import (
    load_mapear_results,
)


def candidate(kind, accepted, bbox):
    return {
        "bbox": bbox, "segmenter_confidence": 0.91, "candidate_type": kind,
        "features": {
            "candidate": accepted, "candidate_type": kind, "reason": kind,
            "interior_pixels": 140, "saturated_ratio": 0.01,
            "dominant_hue_ratio": 0.0, "gray_std_bright_pixels": 9.4,
            "chroma_ratio_bright_pixels": 0.8,
        },
    }


class BubbleSommelierMapearResultsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.chapter = "1"
        self.chapter_dir = (self.root / "FLUXO_SECUNDARIO/04_TEXTO_OFF/"
                            "TO_MERGED_NIVEL_III/1")
        (self.chapter_dir / "json").mkdir(parents=True)

    def tearDown(self):
        self.temporary.cleanup()

    def write_mapear(self, report):
        report_path = self.chapter_dir / "json/styled-balloon-report.json"
        report_path.write_text(json.dumps(report), encoding="utf-8")
        (self.chapter_dir / "json/clean-manifest.json").write_text(
            json.dumps({"report": "json/styled-balloon-report.json"}), encoding="utf-8")
        return report_path

    def valid_report(self, candidates=None):
        return {"pages": [{"source": "page-013-016.png",
                            "styled_balloon_candidates": candidates or []}]}

    def test_filters_only_true_soft_gradient_candidates(self):
        self.write_mapear(self.valid_report([
            candidate("soft_gradient", True, [1, 2, 3, 4]),
            candidate("soft_gradient", False, [5, 6, 7, 8]),
            candidate("irregular_outline", True, [9, 10, 11, 12]),
            candidate("saturated_styled", True, [13, 14, 15, 16]),
        ]))
        result = load_mapear_results(self.root, self.chapter)
        self.assertTrue(result["available"])
        self.assertEqual(result["soft_gradient"]["count"], 1)
        self.assertEqual(result["soft_gradient"]["occurrences"][0]["bbox"], [1, 2, 3, 4])

    def test_preserves_page_bbox_confidence_and_original_features(self):
        source = candidate("soft_gradient", True, [21, 22, 23, 24])
        self.write_mapear(self.valid_report([source]))
        item = load_mapear_results(self.root, self.chapter)["soft_gradient"]["occurrences"][0]
        self.assertEqual(item["page"], "page-013-016.png")
        self.assertEqual(item["bbox"], source["bbox"])
        self.assertEqual(item["segmenter_confidence"], source["segmenter_confidence"])
        self.assertTrue(item["candidate"])
        self.assertEqual(item["candidate_type"], "soft_gradient")
        for field, value in source["features"].items():
            self.assertEqual(item[field], value)
        self.assertEqual(item["features"], source["features"])

    def test_existing_report_without_soft_gradient_has_zero_count(self):
        self.write_mapear(self.valid_report([candidate("irregular_outline", True, [1, 2, 3, 4])]))
        result = load_mapear_results(self.root, self.chapter)
        self.assertTrue(result["available"])
        self.assertEqual(result["soft_gradient"], {"count": 0, "occurrences": []})

    def test_missing_report_is_optional(self):
        result = load_mapear_results(self.root, self.chapter)
        self.assertFalse(result["available"])
        self.assertEqual(result["status"], "unavailable")

    def test_invalid_json_is_diagnostic_not_exception(self):
        report_path = self.write_mapear(self.valid_report())
        report_path.write_text("{invalid", encoding="utf-8")
        result = load_mapear_results(self.root, self.chapter)
        self.assertFalse(result["available"])
        self.assertEqual(result["status"], "invalid")
        self.assertEqual(result["diagnostic"], "styled_balloon_report_invalid_json")

    def test_incompatible_contract_is_diagnostic_not_exception(self):
        self.write_mapear({"pages": "not-a-list"})
        result = load_mapear_results(self.root, self.chapter)
        self.assertFalse(result["available"])
        self.assertEqual(result["status"], "invalid")
        self.assertEqual(result["diagnostic"], "styled_balloon_report_invalid_contract")

    def test_bad_occurrence_is_not_silently_ignored(self):
        self.write_mapear(self.valid_report([{"candidate_type": "soft_gradient"}]))
        result = load_mapear_results(self.root, self.chapter)
        self.assertEqual(result["status"], "invalid")

    def test_manifest_reference_resolves_report_through_official_helper(self):
        self.write_mapear(self.valid_report([candidate("soft_gradient", True, [3, 4, 5, 6])]))
        self.assertEqual(load_mapear_results(self.root, self.chapter)["soft_gradient"]["count"], 1)

    def test_execution_adds_mapear_without_changing_sommelier_bubbles(self):
        mapear = self.valid_report([candidate("soft_gradient", True, [7, 8, 9, 10])])
        self.write_mapear(mapear)
        output_dir = (self.root / "FLUXO_SECUNDARIO/04_TEXTO_OFF/"
                      "BUBBLE_SOMMELIER/1")
        output_dir.mkdir(parents=True)
        report_path = output_dir / "report.json"
        original_bubble = {"identity": "page-013-016-bubble-01", "candidate": True,
                           "metrics": {"coverage": 0.8}}
        original = {"status": "completed", "profile_id": "poc_a_v1",
                    "checkpoints": {"result": {"pages": 1, "crops": 1,
                                  "coverageGe075": 1, "candidates": 1}},
                    "pages": [{"page_id": "page-013-016.png",
                               "bubbles": [original_bubble]}]}

        def fake_run(*_args, **_kwargs):
            report_path.write_text(json.dumps(original), encoding="utf-8")

        with patch.object(execution, "validate_profile_id", return_value="poc_a_v1"), \
             patch.object(execution, "merge_dir", return_value=self.root), \
             patch.object(execution, "execution_dir", return_value=output_dir), \
             patch.object(execution, "report_path", return_value=report_path), \
             patch.object(execution, "replace_execution_artifacts", return_value=nullcontext()), \
             patch.object(execution, "run", side_effect=fake_run), \
             patch.object(execution, "validate_report", side_effect=lambda value, _profile: value):
            execution.execute(self.root, [self.chapter], lambda *_: None, "poc_a_v1")

        saved = json.loads(report_path.read_text(encoding="utf-8"))
        mirrored_report = (self.root / "FLUXO_SECUNDARIO/04_TEXTO_OFF/"
                           "03_BUBBLE_SOMMELIER/1/report.json")
        self.assertEqual(json.loads(mirrored_report.read_text(encoding="utf-8")), saved)
        self.assertEqual(saved["mapear"]["soft_gradient"]["count"], 1)
        self.assertEqual(saved["pages"][0]["bubbles"], [original_bubble])
        self.assertEqual(saved["checkpoints"], original["checkpoints"])

    def test_execution_completes_when_mapear_report_is_missing(self):
        output_dir = (self.root / "FLUXO_SECUNDARIO/04_TEXTO_OFF/"
                      "BUBBLE_SOMMELIER/1")
        output_dir.mkdir(parents=True)
        report_path = output_dir / "report.json"
        original = {"status": "completed", "profile_id": "poc_a_v1",
                    "checkpoints": {"result": {"pages": 0, "crops": 0,
                                  "coverageGe075": 0, "candidates": 0}},
                    "pages": []}

        def fake_run(*_args, **_kwargs):
            report_path.write_text(json.dumps(original), encoding="utf-8")

        with patch.object(execution, "validate_profile_id", return_value="poc_a_v1"), \
             patch.object(execution, "merge_dir", return_value=self.root), \
             patch.object(execution, "execution_dir", return_value=output_dir), \
             patch.object(execution, "report_path", return_value=report_path), \
             patch.object(execution, "replace_execution_artifacts", return_value=nullcontext()), \
             patch.object(execution, "run", side_effect=fake_run), \
             patch.object(execution, "validate_report", side_effect=lambda value, _profile: value):
            result = execution.execute(self.root, [self.chapter], lambda *_: None, "poc_a_v1")

        saved = json.loads(report_path.read_text(encoding="utf-8"))
        mirrored_report = (self.root / "FLUXO_SECUNDARIO/04_TEXTO_OFF/"
                           "03_BUBBLE_SOMMELIER/1/report.json")
        self.assertEqual(json.loads(mirrored_report.read_text(encoding="utf-8")), saved)
        self.assertEqual(len(result), 1)
        self.assertFalse(saved["mapear"]["available"])
        self.assertEqual(saved["mapear"]["status"], "unavailable")


if __name__ == "__main__":
    unittest.main()
