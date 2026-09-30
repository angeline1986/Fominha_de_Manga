import unittest
from pathlib import Path

import cv2
import numpy as np

from central_v2.backend.orchestration.textoff_merged.styled_balloon_detector import (
    _tiles, classify_interior, classify_shape,
)


class StyledBalloonDetectorTests(unittest.TestCase):
    def test_initial_patch_examples_map_to_styled_or_soft_gradient_candidates(self):
        assets = Path(__file__).resolve().parents[1] / ".." / "central_v2/frontend/texto_off/especiais/assets"
        expected = {"estilizado_antes.png": "saturated_styled",
                    "degrade_antes.png": "soft_gradient",
                    "gradiente_suave_antes.png": "soft_gradient"}
        for name, kind in expected.items():
            image = cv2.imread(str((assets / name).resolve()))
            height, width = image.shape[:2]
            mask = np.zeros((height, width), dtype=np.uint8)
            cv2.ellipse(mask, (width // 2, height // 2),
                        (int(width * 0.43), int(height * 0.42)), 0, 0, 360, 255, -1)
            with self.subTest(example=name):
                result = classify_interior(image, mask, cv2, np)
                self.assertEqual(result["candidate_type"], kind)

    def test_uniform_saturated_pink_interior_is_initial_candidate(self):
        image = np.zeros((80, 100, 3), dtype=np.uint8)
        image[:] = (180, 80, 230)
        mask = np.full((80, 100), 255, dtype=np.uint8)
        result = classify_interior(image, mask, cv2, np)
        self.assertTrue(result["candidate"])
        self.assertGreaterEqual(result["saturated_ratio"], 0.35)
        self.assertGreaterEqual(result["dominant_hue_ratio"], 0.55)

    def test_uniform_white_balloon_is_not_candidate(self):
        image = np.full((80, 100, 3), 255, dtype=np.uint8)
        mask = np.full((80, 100), 255, dtype=np.uint8)
        result = classify_interior(image, mask, cv2, np)
        self.assertFalse(result["candidate"])
        self.assertEqual(result["reason"], "low_chroma")

    def test_multicolor_saturated_area_is_not_uniform_style_signal(self):
        image = np.zeros((80, 100, 3), dtype=np.uint8)
        image[:, :50] = (0, 0, 255)
        image[:, 50:] = (255, 0, 0)
        mask = np.full((80, 100), 255, dtype=np.uint8)
        result = classify_interior(image, mask, cv2, np)
        self.assertFalse(result["candidate"])

    def test_irregular_burst_shape_is_candidate_but_regular_shape_is_not(self):
        burst = np.array([[80, 120], [280, 120], [320, 70], [350, 120],
                          [550, 120], [510, 190], [550, 340], [350, 300],
                          [280, 400], [250, 300], [80, 340], [120, 220]], dtype=np.int32)
        ellipse = cv2.ellipse2Poly((300, 250), (200, 130), 0, 0, 360, 5)
        self.assertEqual(classify_shape(burst, cv2)["candidate_type"], "irregular_outline")
        self.assertFalse(classify_shape(ellipse, cv2)["candidate"])

    def test_tall_merge_page_is_processed_in_overlapping_tiles(self):
        image = np.zeros((6572, 940, 3), dtype=np.uint8)
        tiles = _tiles(image)
        self.assertGreater(len(tiles), 1)
        for offset, tile in tiles:
            self.assertLessEqual(tile.shape[0], 1800)
        self.assertEqual(tiles[-1][0] + tiles[-1][1].shape[0], image.shape[0])


if __name__ == "__main__":
    unittest.main()
