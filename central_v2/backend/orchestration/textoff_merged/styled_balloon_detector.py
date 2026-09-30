"""Experimental, review-only detector for strongly styled balloons."""
from __future__ import annotations

ALGORITHM = "textoff_level3_styled_balloon_candidates_v4"
MODEL_REPO = "huyvux3005/manga109-segmentation-bubble"
MODEL_FILE = "best.pt"
MODEL_REVISION = "f9a4108c4955136a810e5e92207972f3fb3a65fd"
CONFIDENCE = 0.15
IOU = 0.45
SATURATION_MIN = 70
VALUE_MIN = 70
MIN_SATURATED_RATIO = 0.35
MIN_DOMINANT_HUE_RATIO = 0.55
MIN_INTERIOR_PIXELS = 120
SOFT_GRADIENT_GRAY_STD_MAX = 13.0
SOFT_GRADIENT_CHROMA_RATIO_MIN = 0.05
TILE_HEIGHT = 1800
TILE_OVERLAP = 450
IRREGULAR_MAX_CIRCULARITY = 0.5
IRREGULAR_MAX_SOLIDITY = 0.9


def classify_interior(image, mask, cv2, np) -> dict:
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    interior = mask > 0
    total = int(np.count_nonzero(interior))
    if total < MIN_INTERIOR_PIXELS:
        return _metrics(total, 0.0, 0.0, False, "small_interior")

    pixels = hsv[interior]
    vivid = (pixels[:, 1] >= SATURATION_MIN) & (pixels[:, 2] >= VALUE_MIN)
    vivid_ratio = float(np.mean(vivid))
    dominant_ratio = _dominant_hue_ratio(pixels[vivid, 0], np) if np.any(vivid) else 0.0
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)[interior]
    bright = pixels[:, 2] >= 180
    bright_gray = gray[bright]
    chroma_ratio = float(np.mean(pixels[bright, 1] > 5)) if np.any(bright) else 0.0
    gray_std = float(bright_gray.std()) if bright_gray.size else 0.0

    saturated_style = (vivid_ratio >= MIN_SATURATED_RATIO
                       and dominant_ratio >= MIN_DOMINANT_HUE_RATIO)
    soft_gradient = (gray_std < SOFT_GRADIENT_GRAY_STD_MAX
                     and chroma_ratio >= SOFT_GRADIENT_CHROMA_RATIO_MIN)
    kind = "saturated_styled" if saturated_style else "soft_gradient" if soft_gradient else None
    reason = kind or ("low_chroma" if not np.any(vivid) and chroma_ratio < SOFT_GRADIENT_CHROMA_RATIO_MIN
                      else "style_signal_below_threshold")
    return {
        "interior_pixels": total, "saturated_ratio": round(vivid_ratio, 5),
        "dominant_hue_ratio": round(dominant_ratio, 5),
        "gray_std_bright_pixels": round(gray_std, 5),
        "chroma_ratio_bright_pixels": round(chroma_ratio, 5),
        "candidate": kind is not None, "candidate_type": kind,
        "reason": reason,
    }


def _dominant_hue_ratio(hues, np) -> float:
    bins = np.bincount((hues // 8).astype(np.int32), minlength=23)
    return float(bins.max() / len(hues))


def _metrics(total, vivid_ratio, dominant_ratio, detected, reason):
    return {
        "interior_pixels": total,
        "saturated_ratio": round(vivid_ratio, 5),
        "dominant_hue_ratio": round(dominant_ratio, 5),
        "gray_std_bright_pixels": 0.0, "chroma_ratio_bright_pixels": 0.0,
        "candidate": detected, "candidate_type": None,
        "reason": reason,
    }


def classify_shape(points, cv2) -> dict:
    area = cv2.contourArea(points)
    perimeter = cv2.arcLength(points, True)
    hull_area = cv2.contourArea(cv2.convexHull(points))
    circularity = 4 * 3.141592653589793 * area / (perimeter * perimeter) if perimeter else 0
    solidity = area / hull_area if hull_area else 0
    irregular = area >= 25000 and circularity <= IRREGULAR_MAX_CIRCULARITY \
        and solidity <= IRREGULAR_MAX_SOLIDITY
    return {"candidate": irregular, "candidate_type": "irregular_outline" if irregular else None,
            "circularity": round(float(circularity), 5), "solidity": round(float(solidity), 5)}


def detect_page(source, model, cv2, np) -> dict:
    image = cv2.imread(str(source))
    if image is None:
        raise RuntimeError(f"Imagem consolidada TextOff inválida: {source.name}")
    candidates = []
    detections = []
    for offset, tile in _tiles(image):
        result = model.predict(source=tile, conf=CONFIDENCE, iou=IOU, verbose=False)[0]
        masks = result.masks
        if masks is None:
            continue
        for index, polygon in enumerate(masks.xy, 1):
            points = np.asarray(polygon, dtype=np.int32)
            if len(points) < 3:
                continue
            local_mask = np.zeros(tile.shape[:2], dtype=np.uint8)
            cv2.fillPoly(local_mask, [points], 255)
            x, y, width, height = cv2.boundingRect(points)
            # Tile-edge fragments are incomplete and can produce false shape scores.
            if y <= 8 or y + height >= tile.shape[0] - 8:
                continue
            erode = max(1, min(5, int(round(min(width, height) * 0.025))))
            interior = cv2.erode(local_mask, cv2.getStructuringElement(
                cv2.MORPH_ELLIPSE, (2 * erode + 1, 2 * erode + 1)))
            metrics = classify_interior(tile, interior if np.any(interior) else local_mask, cv2, np)
            shape = classify_shape(points, cv2)
            if not metrics["candidate"] and shape["candidate"]:
                metrics.update({"candidate": True, "candidate_type": shape["candidate_type"],
                                "shape": {"circularity": shape["circularity"],
                                          "solidity": shape["solidity"]}})
            confidence = float(result.boxes.conf[index - 1]) if result.boxes is not None else 0.0
            bbox = [int(x), int(y + offset), int(width), int(height)]
            item = {"bbox": bbox, "segmenter_confidence": round(confidence, 5),
                    "features": metrics}
            if not any(_bbox_iou(bbox, previous["bbox"]) >= 0.55 for previous in detections):
                item["detection"] = len(detections) + 1
                detections.append(item)
            if metrics["candidate"] and not any(_bbox_iou(bbox, prev["bbox"]) >= 0.55
                                                 and prev.get("candidate_type") == metrics["candidate_type"]
                                                 for prev in candidates):
                item["candidate_type"] = metrics["candidate_type"]
                candidates.append(item)
    return {"source": source.name, "segments_examined": len(detections),
            "balloon_analysis": detections,
            "tiles_analyzed": len(_tiles(image)),
            "styled_balloon_candidates": candidates}


def _tiles(image):
    height = image.shape[0]
    if height <= TILE_HEIGHT:
        return [(0, image)]
    step = TILE_HEIGHT - TILE_OVERLAP
    starts = list(range(0, max(1, height - TILE_HEIGHT + 1), step))
    final = height - TILE_HEIGHT
    if starts[-1] != final:
        starts.append(final)
    return [(start, image[start:start + TILE_HEIGHT]) for start in starts]


def _bbox_iou(left, right) -> float:
    lx, ly, lw, lh = left
    rx, ry, rw, rh = right
    overlap_w = max(0, min(lx + lw, rx + rw) - max(lx, rx))
    overlap_h = max(0, min(ly + lh, ry + rh) - max(ly, ry))
    overlap = overlap_w * overlap_h
    union = lw * lh + rw * rh - overlap
    return overlap / union if union else 0.0
