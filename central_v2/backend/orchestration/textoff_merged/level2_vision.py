"""Vision and inpainting primitives for TextOff Merged Level II."""
from __future__ import annotations

import argparse
import gc
import json
import os
from pathlib import Path
import tempfile
import time

import cv2
import numpy as np
from PIL import Image

BASE_DILATION = (3, 3)
AUTHORIZED_DILATION = (9, 9)
LAMA_PADDING = 120
MAX_MPS_PAGES_PER_MODEL = 3
ALGORITHM = "textoff_merged_level2_cleaner_deferred_3x3_9x9_lama_v1"
REFERENCE_RECIPE = "textoff_special_roi_transparent_legacy_v1"
SUPPORTED = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


def _authorized_deferred_mask(deferred: np.ndarray, balloon: np.ndarray) -> np.ndarray:
    """Apply the approved Cleaner→3x3→9x9 recipe inside one detected balloon."""
    mask = cv2.bitwise_and(deferred, (balloon > 0).astype(np.uint8) * 255)
    if not np.any(mask):
        return mask
    base_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, BASE_DILATION)
    authorized_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, AUTHORIZED_DILATION)
    mask = cv2.dilate(mask, base_kernel)
    mask = cv2.dilate(mask, authorized_kernel)
    mask[balloon == 0] = 0
    return mask


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


def _release_inference_cache(device: str | None) -> None:
    """Release per-page inference buffers so long chapters do not exhaust MPS memory."""
    gc.collect()
    if device == "mps":
        import torch
        torch.mps.empty_cache()


def _atomic_json(path: Path, payload: dict) -> None:
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    os.close(fd)
    tmp = Path(name)
    try:
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)
