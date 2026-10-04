import tempfile
import unittest
from pathlib import Path

from central_v2.backend.orchestration.textoff_merged.artifact_paths import artifact_ref
from central_v2.backend.orchestration.textoff_merged.level2 import _validated_candidate_pages


class TextoffLevel2UnchangedContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.staged = root / "staged"
        self.level1 = root / "level1"
        (self.staged / "clean").mkdir(parents=True)
        (self.staged / "mask").mkdir()
        (self.level1 / "clean").mkdir(parents=True)
        self.candidates = [f"page-{index:03d}-{index + 1:03d}.png" for index in range(10)]
        self.report = {"pages_analyzed": 10, "integrity_ok": True, "pages": []}
        for index, source in enumerate(self.candidates):
            clean = artifact_ref("clean", Path(source).stem + "_clean.png") if index < 8 else None
            level1_clean = artifact_ref("clean", Path(source).stem + "_clean.png")
            mask = artifact_ref("mask", Path(source).stem + "_text_mask.png")
            (self.level1 / level1_clean).write_bytes(b"level1")
            (self.staged / mask).write_bytes(b"mask")
            if clean is not None:
                (self.staged / clean).write_bytes(b"level2")
            self.report["pages"].append({
                "source": source, "clean": clean, "level1_clean": level1_clean,
                "mask": mask, "changed_pixels": 1 if clean else 0,
                "changed_outside_mask": 0, "mask_pixels": 1,
            })

    def test_mixed_ten_candidates_accepts_eight_outputs_and_two_level1_fallbacks(self):
        pages = _validated_candidate_pages(self.report, set(self.candidates), self.staged, self.level1)
        self.assertEqual(len(pages), 10)
        self.assertEqual(sum(item["clean"] is not None for item in pages), 8)
        self.assertEqual(sum(item["clean"] is None for item in pages), 2)

    def test_all_changed_candidates_are_valid(self):
        for item in self.report["pages"][8:]:
            clean = item["level1_clean"]
            item.update(clean=clean, changed_pixels=3)
            (self.staged / clean).write_bytes(b"level2")
        pages = _validated_candidate_pages(self.report, set(self.candidates), self.staged, self.level1)
        self.assertTrue(all(item["clean"] for item in pages))

    def test_all_unchanged_candidates_are_valid(self):
        for item in self.report["pages"]:
            item.update(clean=None, changed_pixels=0)
        pages = _validated_candidate_pages(self.report, set(self.candidates), self.staged, self.level1)
        self.assertTrue(all(item["clean"] is None for item in pages))

    def test_missing_candidate_result_is_rejected(self):
        self.report["pages"].pop()
        with self.assertRaisesRegex(RuntimeError, "não analisou todas"):
            _validated_candidate_pages(self.report, set(self.candidates), self.staged, self.level1)

    def test_referenced_clean_file_missing_is_rejected(self):
        missing = self.report["pages"][0]["clean"]
        (self.staged / missing).unlink()
        with self.assertRaisesRegex(RuntimeError, "PNG clean inválido"):
            _validated_candidate_pages(self.report, set(self.candidates), self.staged, self.level1)

    def test_missing_mask_is_rejected(self):
        missing = self.report["pages"][0]["mask"]
        (self.staged / missing).unlink()
        with self.assertRaisesRegex(RuntimeError, "máscara analítica válida"):
            _validated_candidate_pages(self.report, set(self.candidates), self.staged, self.level1)


if __name__ == "__main__":
    unittest.main()
