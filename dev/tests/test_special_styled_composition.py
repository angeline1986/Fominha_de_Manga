"""Pixel-level composition contracts for Artístico reexecution."""
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

import cv2
import numpy as np

from central_v2.backend.orchestration.textoff_merged.special_styled_composition import compose_delta
from central_v2.backend.orchestration.textoff_special.artifacts import sha256


class StyledCompositionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = np.full((3, 3, 4), (10, 20, 30, 255), dtype=np.uint8)
        self.technical = self.source.copy()
        self.technical[0, 0] = (50, 60, 70, 255)
        self.technical[0, 1, 3] = 90
        self.prior = self.source.copy()
        self.prior[2, 2] = (80, 70, 60, 255)
        self.current = self.prior.copy()
        self.current[2, 0] = (1, 2, 3, 200)
        for name, image in (("source.png", self.source), ("technical.png", self.technical),
                            ("prior.png", self.prior), ("current.png", self.current)):
            self._write(name, image)
        mask = np.zeros((3, 3), dtype=np.uint8)
        mask[0, 0:2] = 255
        self._write("mask.png", mask)
        self.run_dir = self.root / "run"
        (self.run_dir / "treatment").mkdir(parents=True)
        self._write("run/treatment/mask.png", mask)
        self._write("run/treatment/technical.png", self.technical)
        self.run = {"run_id": "run1", "run_dir": str(self.run_dir),
            "result_file": "treatment/technical.png",
            "treatment": {"artifacts": {"authorized_mask": "mask.png"}},
            "artifacts": {"treatment/mask.png": sha256(self.run_dir / "treatment/mask.png")},
            "validation": {"result_sha256": sha256(self.run_dir / "treatment/technical.png")}}
        self.detection = {"path": str(self.root / "source.png"), "sha256": sha256(self.root / "source.png"),
            "prior_output": str(self.root / "prior.png"), "prior_output_sha256": sha256(self.root / "prior.png")}
        self.current_path = self.root / "current.png"

    def _write(self, name, image):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        self.assertTrue(cv2.imwrite(str(path), image))
        return path

    def _compose(self, destination):
        return compose_delta(self.root, "1", "page.png", self.detection,
            self.current_path, sha256(self.current_path),
            {"origin": "PINCEL_DEGRADE"}, self.run, destination)

    def test_composition_preserves_rgba_and_later_pixels(self):
        output = self.root / "composed.png"
        with patch("central_v2.backend.orchestration.textoff_merged.special_styled_composition._verify_lineage"):
            self._compose(output)
        actual = cv2.imread(str(output), cv2.IMREAD_UNCHANGED)
        expected = self.current.copy()
        expected[0, 0:2] = self.technical[0, 0:2]
        np.testing.assert_array_equal(actual, expected)
        self.assertEqual(actual.shape[2], 4)

    def test_overlapping_pixels_block_composition(self):
        changed = self.current.copy()
        changed[0, 0] = (2, 2, 2, 255)
        self._write("current.png", changed)
        with patch("central_v2.backend.orchestration.textoff_merged.special_styled_composition._verify_lineage"):
            with self.assertRaisesRegex(ValueError, "sobrepostos"):
                self._compose(self.root / "blocked.png")

    def test_replacement_removes_old_pixels_even_when_new_delta_is_smaller(self):
        from central_v2.backend.orchestration.textoff_merged.special_styled_composition import compose_occurrence
        old = self.source.copy()
        old[0, 0] = (50, 60, 70, 255)
        old[0, 1] = (50, 60, 70, 255)
        old[1, 0] = (50, 60, 70, 255)
        self._write("prior.png", old)
        self._write("current.png", old)
        new = self.source.copy()
        new[0, 0] = (90, 80, 70, 255)
        new[1, 1] = (90, 80, 70, 255)
        self._write("run/treatment/technical.png", new)
        self.run["validation"]["result_sha256"] = sha256(self.run_dir / "treatment/technical.png")
        mask = np.zeros((3, 3), dtype=np.uint8)
        mask[0, 0:2] = 255
        mask[1, 0] = 255
        old_mask = self._write("old_mask.png", mask)
        mask[1, 1] = 255
        new_mask = self._write("run/treatment/mask.png", mask)
        self.run["artifacts"]["treatment/mask.png"] = sha256(new_mask)
        self.detection["prior_output_sha256"] = sha256(self.root / "prior.png")
        self.detection["occurrence"] = {"mask_path": str(old_mask), "mask_sha256": sha256(old_mask)}
        with patch("central_v2.backend.orchestration.textoff_merged.special_styled_composition._verify_lineage"):
            compose_occurrence(self.root, "1", "page.png", self.detection,
                self.current_path, sha256(self.current_path), {"origin": "PINCEL_ARTISTICO"},
                self.run, self.root / "replaced.png")
        actual = cv2.imread(str(self.root / "replaced.png"), cv2.IMREAD_UNCHANGED)
        expected = self.source.copy()
        expected[0, 0] = new[0, 0]
        expected[1, 1] = new[1, 1]
        np.testing.assert_array_equal(actual, expected)

    def test_replacement_blocks_later_write_on_old_only_pixel(self):
        from central_v2.backend.orchestration.textoff_merged.special_styled_composition import compose_occurrence
        old = self.source.copy()
        old[0, 0] = (50, 60, 70, 255)
        self._write("prior.png", old)
        current = old.copy()
        current[0, 0] = (4, 5, 6, 255)
        self._write("current.png", current)
        new = self.source.copy()
        new[0, 1] = (90, 80, 70, 255)
        self._write("run/treatment/technical.png", new)
        self.run["validation"]["result_sha256"] = sha256(self.run_dir / "treatment/technical.png")
        mask = np.zeros((3, 3), dtype=np.uint8)
        mask[0, 0] = 255
        mask_path = self._write("old_mask.png", mask)
        self.detection["prior_output_sha256"] = sha256(self.root / "prior.png")
        self.detection["occurrence"] = {"mask_path": str(mask_path),
                                         "mask_sha256": sha256(mask_path)}
        with patch("central_v2.backend.orchestration.textoff_merged.special_styled_composition._verify_lineage"):
            with self.assertRaisesRegex(ValueError, "tratamento posterior"):
                compose_occurrence(self.root, "1", "page.png", self.detection,
                    self.current_path, sha256(self.current_path),
                    {"origin": "PINCEL_DEGRADE"}, self.run, self.root / "blocked.png")
        self.assertFalse((self.root / "blocked.png").exists())

    def test_replacement_blocks_coincident_downstream_authorization(self):
        from central_v2.backend.orchestration.textoff_merged.special_styled_composition import compose_occurrence
        from central_v2.backend.orchestration.textoff_merged.stages import stage_chapter
        old = self.source.copy()
        old[0, 0] = (50, 60, 70, 255)
        self._write("prior.png", old)
        self._write("current.png", old)
        self._write("run/treatment/technical.png", self.source)
        self.run["validation"]["result_sha256"] = sha256(self.run_dir / "treatment/technical.png")
        mask = np.zeros((3, 3), dtype=np.uint8)
        mask[0, 0] = 255
        mask_path = self._write("old_mask.png", mask)
        self.detection["prior_output_sha256"] = sha256(self.root / "prior.png")
        self.detection["occurrence"] = {"mask_path": str(mask_path),
                                         "mask_sha256": sha256(mask_path)}
        stage = stage_chapter(self.root, "PINCEL_DEGRADE", "1", read_legacy=False)
        downstream = self._write(str((stage / "authorship/degrade/mask.png").relative_to(self.root)), mask)
        self.detection["dependencies"] = [{"stage": "PINCEL_DEGRADE",
            "write_mask": {"artifact": str(downstream.relative_to(stage)),
                           "sha256": sha256(downstream)}}]
        with patch("central_v2.backend.orchestration.textoff_merged.special_styled_composition._verify_lineage"):
            with self.assertRaisesRegex(ValueError, "máscara de tratamento posterior"):
                compose_occurrence(self.root, "1", "page.png", self.detection,
                    self.current_path, sha256(self.current_path),
                    {"origin": "PINCEL_DEGRADE"}, self.run, self.root / "blocked.png")

    def test_replacement_preserves_independent_downstream_write(self):
        from central_v2.backend.orchestration.textoff_merged.special_styled_composition import compose_occurrence
        from central_v2.backend.orchestration.textoff_merged.stages import stage_chapter
        old = self.source.copy()
        old[0, 0] = (50, 60, 70, 255)
        self._write("prior.png", old)
        current = old.copy()
        current[2, 0] = (4, 5, 6, 255)
        self._write("current.png", current)
        new = self.source.copy()
        new[0, 1] = (90, 80, 70, 255)
        self._write("run/treatment/technical.png", new)
        self.run["validation"]["result_sha256"] = sha256(self.run_dir / "treatment/technical.png")
        old_mask = np.zeros((3, 3), dtype=np.uint8)
        old_mask[0, 0] = 255
        mask_path = self._write("old_mask.png", old_mask)
        self.detection["prior_output_sha256"] = sha256(self.root / "prior.png")
        self.detection["occurrence"] = {"mask_path": str(mask_path),
                                         "mask_sha256": sha256(mask_path)}
        later_mask = np.zeros((3, 3), dtype=np.uint8)
        later_mask[2, 0] = 255
        stage = stage_chapter(self.root, "PINCEL_DEGRADE", "1", read_legacy=False)
        later_path = self._write(str((stage / "authorship/degrade/mask.png").relative_to(self.root)), later_mask)
        self.detection["dependencies"] = [{"stage": "PINCEL_DEGRADE",
            "write_mask": {"artifact": str(later_path.relative_to(stage)),
                           "sha256": sha256(later_path)}}]
        with patch("central_v2.backend.orchestration.textoff_merged.special_styled_composition._verify_lineage"):
            compose_occurrence(self.root, "1", "page.png", self.detection,
                self.current_path, sha256(self.current_path), {"origin": "PINCEL_DEGRADE"},
                self.run, self.root / "independent.png")
        actual = cv2.imread(str(self.root / "independent.png"), cv2.IMREAD_UNCHANGED)
        expected = current.copy()
        expected[0, 0] = self.source[0, 0]
        expected[0, 1] = new[0, 1]
        np.testing.assert_array_equal(actual, expected)

    def test_hash_mismatch_and_unauthorized_delta_block_composition(self):
        self.detection["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "Snapshot histórico"):
            self._compose(self.root / "blocked.png")
        self.detection["sha256"] = sha256(self.root / "source.png")
        mask = np.zeros((3, 3), dtype=np.uint8)
        mask[0, 0] = 255
        mask_path = self._write("run/treatment/mask.png", mask)
        self.run["artifacts"]["treatment/mask.png"] = sha256(mask_path)
        with patch("central_v2.backend.orchestration.textoff_merged.special_styled_composition._verify_lineage"):
            with self.assertRaisesRegex(ValueError, "fora da máscara"):
                self._compose(self.root / "blocked.png")
        self.run["treatment"]["artifacts"]["authorized_mask"] = "missing.png"
        with self.assertRaises(ValueError):
            self._compose(self.root / "blocked.png")


if __name__ == "__main__":
    unittest.main()
