import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np
from PIL import Image, ImageDraw

from bubble_cleaner_v2 import (
    Balloon,
    build_authorized_mask,
    clean,
    containment_ratio,
    polygon_mask,
)


class BubbleCleanerV2Tests(unittest.TestCase):
    def test_text_outside_balloon_is_preserved(self):
        rgb = np.full((300, 300, 3), 255, dtype=np.uint8)
        balloon_mask = np.zeros((300, 300), dtype=np.uint8)
        cv2.circle(balloon_mask, (150, 100), 70, 255, -1)

        balloons = [Balloon(
            id=1, x=80, y=30, w=140, h=140, area=10000,
            contour_area=10000.0, fill_ratio=0.7, brightness=250.0,
            texture=5.0, boundary_margin=8, score=0.9
        )]
        ocr = [
            ([[120, 80], [180, 80], [180, 100], [120, 100]], "HELLO", 0.95),
            ([[20, 240], [100, 240], [100, 260], [20, 260]], "BOOM", 0.99),
        ]

        mask, decisions = build_authorized_mask(
            rgb, balloons, {1: balloon_mask}, ocr
        )

        self.assertEqual(decisions[0].decision, "auto_clean")
        self.assertEqual(decisions[1].decision, "preserve")
        self.assertGreater(np.count_nonzero(mask), 0)

    def test_low_confidence_ocr_is_preserved(self):
        rgb = np.full((200, 200, 3), 255, dtype=np.uint8)
        balloon_mask = np.full((200, 200), 255, dtype=np.uint8)
        balloons = [Balloon(
            id=1, x=0, y=0, w=200, h=200, area=40000,
            contour_area=40000.0, fill_ratio=1.0, brightness=255.0,
            texture=0.0, boundary_margin=8, score=0.99
        )]
        ocr = [
            ([[50, 50], [150, 50], [150, 70], [50, 70]], "maybe", 0.20),
        ]
        mask, decisions = build_authorized_mask(
            rgb, balloons, {1: balloon_mask}, ocr
        )
        self.assertEqual(decisions[0].decision, "preserve")
        self.assertEqual(np.count_nonzero(mask), 0)

    def test_clean_without_mask_is_identity(self):
        rgb = np.random.default_rng(1).integers(0, 255, (50, 50, 3), dtype=np.uint8)
        mask = np.zeros((50, 50), dtype=np.uint8)
        out = clean(rgb, mask)
        self.assertTrue(np.array_equal(rgb, out))


if __name__ == "__main__":
    unittest.main()
