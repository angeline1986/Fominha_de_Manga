import unittest

import cv2
import numpy as np

from processamento.limpeza_baloes.cleaner_v2.transparency_classifier import measure_transparency


class CleanerV2TransparencyClassifierTests(unittest.TestCase):
    def setUp(self):
        self.mask = np.zeros((240, 320), dtype=np.uint8)
        cv2.ellipse(self.mask, (160, 120), (120, 80), 0, 0, 360, 255, -1)

    def test_opaque_white_balloon_with_dark_text_is_not_transparent(self):
        image = np.full((240, 320, 3), 255, dtype=np.uint8)
        cv2.putText(image, "TEXT", (90, 130), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 3)
        self.assertFalse(measure_transparency(image, self.mask)["transparent"])

    def test_faded_color_and_texture_inside_balloon_are_detected(self):
        image = np.full((240, 320, 3), 255, dtype=np.uint8)
        underlay = np.zeros_like(image)
        underlay[:, :160] = (40, 120, 220)
        underlay[:, 160:] = (170, 80, 30)
        image[self.mask > 0] = cv2.addWeighted(
            image, 0.68, underlay, 0.32, 0
        )[self.mask > 0]
        result = measure_transparency(image, self.mask)
        self.assertTrue(result["transparent"])
        self.assertEqual(result["reason"], "scene_visible_through_interior")


if __name__ == "__main__":
    unittest.main()
