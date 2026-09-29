"""Conservative image-space transparency signal for segmented speech balloons."""
from __future__ import annotations


GRAY_STD_THRESHOLD = 9.0
CHROMA_THRESHOLD = 5
CHROMA_RATIO_THRESHOLD = 0.05
MIN_SAMPLE_PIXELS = 500


def measure_transparency(image_bgr, interior_mask) -> dict:
    """Detect visible scene variation inside a balloon, ignoring dark lettering."""
    import cv2
    import numpy as np

    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
    sample = (interior_mask > 0) & (gray >= 200)
    values = gray[sample]
    saturation = hsv[:, :, 1][sample]
    if values.size < MIN_SAMPLE_PIXELS:
        return {
            "transparent": False,
            "sample_pixels": int(values.size),
            "gray_std": 0.0,
            "chroma_ratio": 0.0,
            "reason": "insufficient_bright_interior",
        }

    gray_std = float(values.std())
    chroma_ratio = float(np.mean(saturation > CHROMA_THRESHOLD))
    transparent = (
        gray_std >= GRAY_STD_THRESHOLD
        or chroma_ratio >= CHROMA_RATIO_THRESHOLD
    )
    return {
        "transparent": transparent,
        "sample_pixels": int(values.size),
        "gray_std": round(gray_std, 3),
        "chroma_ratio": round(chroma_ratio, 5),
        "reason": "scene_visible_through_interior" if transparent else "uniform_interior",
    }
