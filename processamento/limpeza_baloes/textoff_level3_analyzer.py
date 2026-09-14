from __future__ import annotations

from collections import deque
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from processamento.limpeza_baloes.textoff_level3 import (
    STATUS_PENDING,
    _clean_dir,
    _normalize_stage,
    _validate_image_name,
    pending_for_chapter,
)

ALGORITHM = "textoff_level3_uniform_residual_v1"


def _components(mask: np.ndarray):
    h, w = mask.shape
    seen = np.zeros(mask.shape, dtype=np.uint8)
    out = []
    for y in range(h):
        for x in np.flatnonzero(mask[y] & (seen[y] == 0)):
            x = int(x)
            if seen[y, x]:
                continue
            q = deque([(x, y)])
            seen[y, x] = 1
            minx = maxx = x
            miny = maxy = y
            count = 0
            while q:
                cx, cy = q.popleft()
                count += 1
                minx, maxx = min(minx, cx), max(maxx, cx)
                miny, maxy = min(miny, cy), max(maxy, cy)
                for nx, ny in ((cx-1,cy),(cx+1,cy),(cx,cy-1),(cx,cy+1)):
                    if 0 <= nx < w and 0 <= ny < h and mask[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = 1
                        q.append((nx, ny))
            out.append((minx, miny, maxx-minx+1, maxy-miny+1, count))
    return out


def _merge_boxes(boxes, gap=18):
    boxes = list(boxes)
    changed = True
    while changed:
        changed = False
        result = []
        while boxes:
            x, y, w, h = boxes.pop(0)
            x2, y2 = x+w, y+h
            merged = False
            for i, (a, b, c, d) in enumerate(boxes):
                a2, b2 = a+c, b+d
                if not (x2+gap < a or a2+gap < x or y2+gap < b or b2+gap < y):
                    nx, ny = min(x,a), min(y,b)
                    nx2, ny2 = max(x2,a2), max(y2,b2)
                    boxes[i] = (nx, ny, nx2-nx, ny2-ny)
                    changed = True
                    merged = True
                    break
            if not merged:
                result.append((x,y,w,h))
        boxes = result
    return boxes


def analyze_image(path: Path) -> dict[str, Any]:
    rgb = np.asarray(Image.open(path).convert("RGB"))
    gray = np.round(rgb.mean(axis=2)).astype(np.uint8)
    height, width = gray.shape
    boxes = []

    for x, y, w, h, pixels in _components(gray <= 175):
        if pixels < 14 or pixels > 5000 or w < 2 or h < 3 or w > 140 or h > 140:
            continue
        pad = 14
        x0, y0 = max(0,x-pad), max(0,y-pad)
        x1, y1 = min(width,x+w+pad), min(height,y+h+pad)
        context = gray[y0:y1, x0:x1]
        ring = np.ones(context.shape, dtype=bool)
        rx, ry = x-x0, y-y0
        ring[ry:ry+h, rx:rx+w] = False
        vals = context[ring]
        if vals.size < 80:
            continue
        if float(vals.mean()) < 236 or float(vals.std()) > 10.0 or float((vals >= 225).mean()) < 0.90:
            continue
        boxes.append((x,y,w,h))

    candidates = []
    for x,y,w,h in _merge_boxes(boxes):
        if w > 360 or h > 180 or w*h > 45000:
            continue
        candidates.append({"id": len(candidates)+1, "bbox": [int(x),int(y),int(w),int(h)]})

    return {
        "algorithm": ALGORITHM,
        "image_width": int(width),
        "image_height": int(height),
        "count": len(candidates),
        "candidates": candidates,
    }


def analyze_residual_job(manga: Path, chs, payload: dict[str, Any]) -> dict[str, Any]:
    if len(chs) != 1:
        raise ValueError("Selecione exatamente um capítulo para analisar.")
    chapter = str(payload.get("chapter") or "").strip()
    stage = _normalize_stage(payload.get("source_stage"))
    source_file = _validate_image_name(payload.get("source_file"), "Imagem original")
    clean_file = _validate_image_name(payload.get("clean_file"), "Imagem limpa")
    if not chapter:
        raise ValueError("Capítulo não informado.")

    item = pending_for_chapter(manga, chapter).get(f"{stage}:{source_file}")
    if not isinstance(item, dict) or item.get("status") != STATUS_PENDING:
        raise ValueError("A imagem não está pendente no Texto Off — Nível III.")
    if str(item.get("clean_file") or "") != clean_file:
        raise ValueError("O resultado atual não corresponde à pendência registrada.")

    clean_path = _clean_dir(manga, chapter, stage) / clean_file
    if not clean_path.is_file():
        raise FileNotFoundError(f"Resultado atual não encontrado: {clean_file}")

    return {
        "status": "ANALISADO",
        "chapter": chapter,
        "source_stage": stage,
        "source_file": source_file,
        "clean_file": clean_file,
        **analyze_image(clean_path),
    }
