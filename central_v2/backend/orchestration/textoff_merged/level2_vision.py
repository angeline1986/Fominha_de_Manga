"""Vision and inpainting primitives for TextOff Merged Level II."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import tempfile
import time

import cv2
import numpy as np
from PIL import Image

MIN_BOX_PIXELS = 36
DARK_THRESHOLD = 225
BASE_DILATION = 3
AUTHORIZED_DILATION = 9
LAMA_PADDING = 120
ALGORITHM = "textoff_merged_level2_cleaner_mask_craft_lama_transparent_v2"
SUPPORTED = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


def _boxes(reader, crop: np.ndarray) -> list[np.ndarray]:
    horizontal, free = reader.detect(crop, min_size=8, text_threshold=0.55,
                                    low_text=0.35, link_threshold=0.35,
                                    canvas_size=2560, mag_ratio=1.5)
    result = []
    for x1, x2, y1, y2 in (horizontal[0] if horizontal else []):
        result.append(np.asarray([[x1, y1], [x2, y1], [x2, y2], [x1, y2]], dtype=np.int32))
    for polygon in (free[0] if free else []):
        points = np.asarray(polygon, dtype=np.int32).reshape((-1, 2))
        if len(points) >= 4:
            result.append(points)
    return result


def _balloon_text_mask(rgb: np.ndarray, label_mask: np.ndarray,
                       bbox: list[int], reader,
                       deferred_mask: np.ndarray | None = None) -> tuple[np.ndarray, list[dict]]:
    x, y, width, height = map(int, bbox)
    h, w = label_mask.shape
    x0, y0, x1, y1 = max(0, x), max(0, y), min(w, x + width), min(h, y + height)
    balloon = label_mask[y0:y1, x0:x1]
    crop = rgb[y0:y1, x0:x1]
    gray = cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY)
    mask = np.zeros(balloon.shape, dtype=np.uint8)
    decisions = []
    if deferred_mask is not None:
        deferred = deferred_mask[y0:y1, x0:x1]
        deferred = cv2.bitwise_and(deferred, balloon.astype(np.uint8) * 255)
        mask = cv2.bitwise_or(mask, deferred)
        pixels = int(np.count_nonzero(deferred))
        if pixels:
            decisions.append({"decision": "include", "source": "level1_deferred_cleaner_mask",
                              "ink_pixels": pixels})

    for polygon in _boxes(reader, crop):
        box_mask = np.zeros(balloon.shape, dtype=np.uint8)
        cv2.fillPoly(box_mask, [polygon], 255)
        area = int(np.count_nonzero(box_mask))
        if area < MIN_BOX_PIXELS:
            continue
        interior = balloon > 0
        inside = int(np.count_nonzero((box_mask > 0) & interior))
        containment = inside / area
        if containment < 0.94:
            decisions.append({"decision": "preserve", "reason": "text_box_crosses_balloon_boundary",
                              "containment": round(containment, 4)})
            continue

        dark = (gray <= DARK_THRESHOLD) & (box_mask > 0) & interior
        count, labels, stats, _ = cv2.connectedComponentsWithStats(dark.astype(np.uint8), 8)
        selected = np.zeros(balloon.shape, dtype=np.uint8)
        for component in range(1, count):
            pixels = int(stats[component, cv2.CC_STAT_AREA])
            if pixels >= 2 and pixels <= max(120, int(area * 0.18)):
                selected[labels == component] = 255
        ink = int(np.count_nonzero(selected))
        if ink < 6 or ink / area > 0.45:
            decisions.append({"decision": "preserve", "reason": "text_ink_ratio_out_of_range",
                              "containment": round(containment, 4), "ink_pixels": ink})
            continue

        mask = cv2.bitwise_or(mask, selected)
        decisions.append({"decision": "inpaint", "containment": round(containment, 4),
                          "box_pixels": area, "ink_pixels": ink})

    if np.any(mask):
        base_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE,
                                                (BASE_DILATION, BASE_DILATION))
        authorized_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE,
                                                      (AUTHORIZED_DILATION, AUTHORIZED_DILATION))
        mask = cv2.dilate(mask, base_kernel)
        mask = cv2.dilate(mask, authorized_kernel)
        mask[~(balloon > 0)] = 0
    full = np.zeros(label_mask.shape, dtype=np.uint8)
    full[y0:y1, x0:x1] = mask
    return full, decisions


def _lama_model():
    from simple_lama_inpainting import SimpleLama
    candidates = []
    if os.environ.get("LAMA_MODEL"):
        candidates.append(Path(os.environ["LAMA_MODEL"]).expanduser())
    home = Path.home()
    candidates.extend([
        home / "Library/Caches/pcleaner/model/anime-manga-big-lama.pt",
        home / ".cache/pcleaner/model/anime-manga-big-lama.pt",
    ])
    model_path = next((path.resolve() for path in candidates if path.is_file()), None)
    if model_path is None:
        raise FileNotFoundError("Modelo anime-manga-big-lama.pt não encontrado; Nível II foi cancelado sem promover resultados.")
    os.environ["LAMA_MODEL"] = str(model_path)
    import torch
    device = torch.device("mps") if torch.backends.mps.is_available() else torch.device("cpu")
    return SimpleLama(device=device), str(model_path), str(device)


def _inpaint(rgb: np.ndarray, mask: np.ndarray, model) -> np.ndarray:
    ys, xs = np.where(mask > 0)
    if not len(xs):
        return rgb.copy()
    pad = LAMA_PADDING
    x0, y0 = max(0, int(xs.min()) - pad), max(0, int(ys.min()) - pad)
    x1, y1 = min(rgb.shape[1], int(xs.max()) + pad + 1), min(rgb.shape[0], int(ys.max()) + pad + 1)
    source = Image.fromarray(rgb[y0:y1, x0:x1])
    local_mask = Image.fromarray(mask[y0:y1, x0:x1], mode="L")
    rebuilt = model(source, local_mask).convert("RGB")
    if rebuilt.size != source.size:
        rebuilt = rebuilt.crop((0, 0, source.width, source.height))
    result = np.asarray(rebuilt)
    output = rgb.copy()
    region = output[y0:y1, x0:x1]
    local = mask[y0:y1, x0:x1] > 0
    region[local] = result[local]
    output[y0:y1, x0:x1] = region
    return output


def _atomic_json(path: Path, payload: dict) -> None:
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    os.close(fd)
    tmp = Path(name)
    try:
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)
