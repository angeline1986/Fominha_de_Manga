"""Special approval may restore only real deferred components touched by Check ROIs."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import cv2
import numpy as np

from processamento.limpeza_baloes.textoff_special_approval import apply_approved_rois
from processamento.limpeza_baloes.textoff_special_roi import run_degrade_roi


class SpecialApprovalTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source.png"
        self.clean = self.root / "clean.png"
        self.mask = self.root / "mask.png"
        self.report = self.root / "balloon_authorization.json"
        self.original = np.full((100, 140, 3), 220, np.uint8)
        self.raw_clean = self.original.copy()
        self.raw_mask = np.zeros((100, 140), np.uint8)
        for left in (10, 60, 110):
            self.raw_mask[20:40, left:left + 20] = 255
            self.raw_clean[20:40, left:left + 20] = 180
        self.boxes = [(8, 18, 25, 25), (58, 18, 25, 25)]
        cv2.imwrite(str(self.source), self.original)
        decisions = [{"component": i, "reason": "transparent_balloon_deferred"}
                     for i in range(1, 4)]
        self.report.write_text(json.dumps({"pages": [{"component_decisions": decisions}]}))

    def authorize(self, boxes=None):
        cv2.imwrite(str(self.clean), self.original)
        cv2.imwrite(str(self.mask), np.zeros_like(self.raw_mask))
        return apply_approved_rois(self.original, self.clean, self.mask, self.raw_clean,
                                   self.raw_mask, self.report, self.boxes if boxes is None else boxes)

    def test_two_approved_rois_restore_only_two_deferred_components(self):
        selected = self.authorize()
        mask = cv2.imread(str(self.mask), cv2.IMREAD_GRAYSCALE)
        self.assertEqual([row["component"] for row in selected], [1, 2])
        self.assertEqual([row["roi_hits"] for row in selected], [[1], [2]])
        self.assertEqual(np.count_nonzero(mask), 800)
        self.assertEqual(np.count_nonzero(mask[20:40, 110:130]), 0)

    def test_empty_roi_does_not_fabricate_authorization(self):
        self.assertEqual(self.authorize([(90, 60, 20, 20)]), [])
        self.assertEqual(np.count_nonzero(cv2.imread(str(self.mask), 0)), 0)

    def test_ordinary_degrade_keeps_transparent_deferral(self):
        def cleaner(_source, target):
            clean, mask = target / "clean.png", target / "mask.png"
            cv2.imwrite(str(clean), self.raw_clean)
            cv2.imwrite(str(mask), self.raw_mask)
            return clean, mask

        def automatic(_source, clean, mask, target):
            cv2.imwrite(str(clean), self.original)
            cv2.imwrite(str(mask), np.zeros_like(self.raw_mask))
            (target / "balloon_authorization.json").write_text(self.report.read_text())

        target = self.root / "run"
        with patch("processamento.limpeza_baloes.patch_degrade_experimento._run_cleaner",
                   side_effect=cleaner), patch(
                   "processamento.limpeza_baloes.patch_degrade_experimento._authorize_balloon",
                   side_effect=automatic):
            with self.assertRaisesRegex(RuntimeError, "Nenhum componente autorizado"):
                run_degrade_roi(self.source, target, [dict(zip(
                    ("x", "y", "width", "height"), self.boxes[0]))])
            with patch("processamento.limpeza_baloes.patch_degrade_experimento._surface",
                       return_value=None), patch(
                       "processamento.limpeza_baloes.patch_degrade_experimento._local_heal",
                       side_effect=RuntimeError("selected and reached heal")):
                with self.assertRaisesRegex(RuntimeError, "selected and reached heal"):
                    run_degrade_roi(self.source, target, [dict(zip(
                        ("x", "y", "width", "height"), box)) for box in self.boxes],
                        approved_check_rois=True)
            mask = cv2.imread(str(target / "roi_authorized_mask.png"), 0)
            self.assertEqual(np.count_nonzero(mask), 800)


if __name__ == "__main__":
    unittest.main()
