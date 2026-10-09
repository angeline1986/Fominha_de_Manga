"""Effective Artístico pixel ownership is retained only when components are exclusive."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import cv2
import numpy as np

from central_v2.backend.orchestration.textoff_merged.special_styled_authorship import masks, persist, verified
from central_v2.backend.orchestration.textoff_special.artifacts import sha256


class AuthorshipTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = np.full((8, 12, 4), (10, 20, 30, 255), dtype=np.uint8)
        self.output = self.source.copy()
        self.output[2, 1] = (50, 60, 70, 255)
        self.output[2, 5] = (80, 90, 100, 255)
        self.output[2, 9] = (120, 130, 140, 255)
        self.mask = np.zeros((8, 12), dtype=np.uint8)
        for x in (1, 5, 9):
            self.mask[2:4, x:x + 2] = 255
        self.ids = ["A", "B", "C"]
        self.rois = [{"x": x, "y": 2, "width": 2, "height": 2} for x in (1, 5, 9)]
        self._write("source.png", self.source)
        self._write("output.png", self.output)
        self._write("authorized.png", self.mask)

    def _write(self, name, pixels):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        self.assertTrue(cv2.imwrite(str(path), pixels))
        return path

    def test_three_separate_components_have_independent_verified_masks(self):
        ownership = persist(self.root, self.root / "source.png", self.root / "output.png",
                            self.root / "authorized.png", self.ids, self.rois, "oldrun")
        for identity, x, roi in zip(self.ids, (1, 5, 9), self.rois):
            paths = verified(self.root, ownership[identity], identity, roi,
                             sha256(self.root / "source.png"))
            changed = cv2.imread(str(paths["changed"]), cv2.IMREAD_GRAYSCALE)
            self.assertEqual(int(np.count_nonzero(changed)), 1)
            self.assertEqual(int(changed[2, x]), 255)

    def test_shared_component_is_ambiguous_and_cannot_be_used_as_proof(self):
        mask = self.mask.copy()
        mask[2, 3:9] = 255
        self._write("authorized.png", mask)
        ownership = masks(self.root / "source.png", self.root / "output.png",
                          self.root / "authorized.png", self.ids, self.rois)
        self.assertTrue(all(item["ambiguous"] for item in ownership.values()))


if __name__ == "__main__":
    unittest.main()
