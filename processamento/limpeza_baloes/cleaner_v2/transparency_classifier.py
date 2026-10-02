"""Conservative image-space transparency signal for segmented speech balloons."""
from __future__ import annotations


GRAY_STD_THRESHOLD = 9.0
CHROMA_THRESHOLD = 5
CHROMA_RATIO_THRESHOLD = 0.05
MIN_SAMPLE_PIXELS = 500
SECONDARY_TEXT_DILATION_PX = 5
SECONDARY_BORDER_ERODE_PX = 3
SECONDARY_NONWHITE_LAB_DISTANCE = 8.0
SECONDARY_NONWHITE_RATIO_THRESHOLD = 0.01


def measure_transparency(image_bgr, interior_mask, raw_cleaner_mask=None) -> dict:
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
    primary_transparent = (
        gray_std >= GRAY_STD_THRESHOLD
        or chroma_ratio >= CHROMA_RATIO_THRESHOLD
    )
    secondary = None
    transparent = primary_transparent
    if not primary_transparent and raw_cleaner_mask is not None:
        secondary = measure_background_safety_gate(
            image_bgr, interior_mask, raw_cleaner_mask
        )
        transparent = secondary["suspected_transparency"]

    reason = "scene_visible_through_interior" if primary_transparent else "uniform_interior"
    if transparent and not primary_transparent:
        reason = "background_scene_visible_after_text_exclusion"

    result = {
        "transparent": transparent,
        "sample_pixels": int(values.size),
        "gray_std": round(gray_std, 3),
        "chroma_ratio": round(chroma_ratio, 5),
        "reason": reason,
    }
    if secondary is not None:
        result["background_safety_gate"] = secondary
    return result


def measure_background_safety_gate(image_bgr, interior_mask, raw_cleaner_mask) -> dict:
    import cv2
    import numpy as np

    if image_bgr.shape[:2] != interior_mask.shape[:2]:
        raise ValueError("Interior do balão e imagem possuem dimensões divergentes.")
    if raw_cleaner_mask.shape[:2] != interior_mask.shape[:2]:
        raise ValueError("Máscara bruta do Cleaner e interior possuem dimensões divergentes.")

    interior = (interior_mask > 0).astype(np.uint8)
    raw = (raw_cleaner_mask > 0).astype(np.uint8)

    if SECONDARY_BORDER_ERODE_PX > 0:
        size = 2 * SECONDARY_BORDER_ERODE_PX + 1
        interior = cv2.erode(
            interior,
            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (size, size)),
        )

    if SECONDARY_TEXT_DILATION_PX > 0:
        size = 2 * SECONDARY_TEXT_DILATION_PX + 1
        raw = cv2.dilate(
            raw,
            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (size, size)),
        )

    analysis = (interior > 0) & (raw == 0)
    analysis_pixels = int(np.count_nonzero(analysis))
    if analysis_pixels < MIN_SAMPLE_PIXELS:
        return {
            "analysis_pixels": analysis_pixels,
            "nonwhite_ratio": 0.0,
            "threshold": SECONDARY_NONWHITE_RATIO_THRESHOLD,
            "suspected_transparency": False,
        }

    lab = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
    white = np.array([255.0, 128.0, 128.0], dtype=np.float32)
    distances = np.linalg.norm(lab[analysis] - white, axis=1)
    nonwhite_ratio = float(np.mean(distances >= SECONDARY_NONWHITE_LAB_DISTANCE))
    return {
        "analysis_pixels": analysis_pixels,
        "nonwhite_ratio": round(nonwhite_ratio, 5),
        "threshold": SECONDARY_NONWHITE_RATIO_THRESHOLD,
        "suspected_transparency": bool(
            nonwhite_ratio >= SECONDARY_NONWHITE_RATIO_THRESHOLD
        ),
    }
