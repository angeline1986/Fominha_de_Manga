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

    def test_opaque_uniform_balloon_with_raw_mask_remains_opaque(self):
        image = np.full((240, 320, 3), 255, dtype=np.uint8)
        raw_mask = np.zeros((240, 320), dtype=np.uint8)
        cv2.putText(raw_mask, "TEXT", (90, 130), cv2.FONT_HERSHEY_SIMPLEX, 1, 255, 3)

        result = measure_transparency(image, self.mask, raw_mask)

        self.assertFalse(result["transparent"])
        self.assertEqual(result["reason"], "uniform_interior")
        self.assertIn("background_safety_gate", result)
        self.assertFalse(
            result["background_safety_gate"]["suspected_transparency"]
        )

    def test_secondary_gate_recovers_primary_false_negative_after_text_exclusion(self):
        image = np.full((240, 320, 3), 255, dtype=np.uint8)
        raw_mask = np.zeros((240, 320), dtype=np.uint8)

        # Pequena região de fundo visível: insuficiente para disparar o
        # classificador primário, mas acima do limiar secundário de 1%.
        image[105:130, 145:175] = (220, 220, 220)

        result = measure_transparency(image, self.mask, raw_mask)

        self.assertTrue(result["transparent"])
        self.assertEqual(
            result["reason"],
            "background_scene_visible_after_text_exclusion",
        )
        self.assertTrue(
            result["background_safety_gate"]["suspected_transparency"]
        )
        self.assertGreaterEqual(
            result["background_safety_gate"]["nonwhite_ratio"],
            result["background_safety_gate"]["threshold"],
        )

    def test_without_raw_mask_preserves_legacy_primary_decision(self):
        image = np.full((240, 320, 3), 255, dtype=np.uint8)
        image[105:130, 145:175] = (220, 220, 220)

        result = measure_transparency(image, self.mask)

        self.assertFalse(result["transparent"])
        self.assertEqual(result["reason"], "uniform_interior")
        self.assertNotIn("background_safety_gate", result)


if __name__ == "__main__":
    unittest.main()
