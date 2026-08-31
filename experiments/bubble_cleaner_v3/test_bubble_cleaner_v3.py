import unittest
import numpy as np

from bubble_cleaner_v3 import (
    Detection,
    authorize,
    clean,
    _robust_local_background,
)


def det(gate_ok=True):
    return Detection(
        id=1, x1=40, y1=30, x2=260, y2=180,
        confidence=0.95, class_id=0, class_name="Text",
        background_brightness=250.0, background_texture=10.0,
        gate_ok=gate_ok, gate_reason="ok" if gate_ok else "rejected",
    )


class BubbleCleanerV33Tests(unittest.TestCase):
    def test_white_background_uses_uniform_fill(self):
        rgb = np.full((100, 140, 3), 248, dtype=np.uint8)
        rgb[40:60, 50:90] = 0
        mask = np.zeros((100, 140), dtype=np.uint8)
        mask[35:65, 45:95] = 255

        cleaned, info = clean(rgb, mask)
        self.assertEqual(info["strategy"], "uniform_local_background")
        self.assertTrue(np.all(cleaned[mask == 0] == rgb[mask == 0]))
        self.assertGreater(float(cleaned[50, 70].mean()), 220)

    def test_non_uniform_background_falls_back(self):
        rgb = np.zeros((100, 140, 3), dtype=np.uint8)
        for y in range(100):
            rgb[y, :, :] = (y * 2) % 255
        mask = np.zeros((100, 140), dtype=np.uint8)
        mask[35:65, 45:95] = 255

        cleaned, info = clean(rgb, mask)
        self.assertEqual(info["strategy"], "telea_fallback")
        self.assertTrue(np.all(cleaned[mask == 0] == rgb[mask == 0]))

    def test_ocr_outside_detection_is_preserved(self):
        rgb = np.full((300, 300, 3), 255, dtype=np.uint8)
        ocr = [
            ([[20, 230], [130, 230], [130, 255], [20, 255]], "BOOM", 0.99),
        ]
        mask, decisions = authorize(rgb, [det()], ocr)
        self.assertEqual(decisions[0].decision, "preserve")
        self.assertEqual(np.count_nonzero(mask), 0)


if __name__ == "__main__":
    unittest.main()
