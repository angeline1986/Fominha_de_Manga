import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

from bubble_cleaner_experimental import analyze_and_clean


class BubbleCleanerExperimentalTests(unittest.TestCase):
    def test_source_is_never_modified_and_outputs_are_created(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "page.png"
            out = root / "out"

            im = Image.new("RGB", (500, 500), "gray")
            d = ImageDraw.Draw(im)
            d.ellipse((80, 100, 420, 330), fill="white", outline="black", width=3)
            d.rectangle((170, 175, 330, 190), fill="black")
            d.rectangle((190, 220, 310, 235), fill="black")
            im.save(src)
            before = src.read_bytes()

            result = analyze_and_clean(src, out)

            self.assertEqual(src.read_bytes(), before)
            self.assertTrue(Path(result.files["mask"]).exists())
            self.assertTrue(Path(result.files["overlay"]).exists())
            self.assertTrue(Path(result.files["cleaned_preview"]).exists())
            self.assertTrue(Path(result.files["report"]).exists())

    def test_integrity_check_rejects_changes_outside_mask(self):
        # The implementation itself must report zero changes outside mask.
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "page.png"
            out = root / "out"

            arr = np.full((300, 300, 3), 210, dtype=np.uint8)
            cv2.rectangle(arr, (50, 50), (250, 220), (255, 255, 255), -1)
            cv2.rectangle(arr, (100, 120), (200, 135), (0, 0, 0), -1)
            Image.fromarray(arr).save(src)

            result = analyze_and_clean(src, out)
            self.assertEqual(result.changed_outside_authorized_mask, 0)
            self.assertTrue(result.integrity_ok)


if __name__ == "__main__":
    unittest.main()
