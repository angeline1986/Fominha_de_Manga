#!/usr/bin/env python3
"""
Experimental conservative speech-bubble cleaner.

Principles:
- Never modifies the source image.
- Only auto-cleans dark connected components that are well inside a large,
  bright, low-texture region.
- Preserves uncertain regions instead of guessing.
- Produces overlay, mask, cleaned preview and JSON report for every image.
- No OCR is required in this first experiment: the goal is to validate
  integrity/safety of the mask before introducing semantic OCR/classification.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np
from PIL import Image


@dataclass
class Candidate:
    x: int
    y: int
    w: int
    h: int
    area: int
    bubble_area: int
    bubble_brightness: float
    bubble_texture: float
    edge_clearance: int
    confidence: float
    decision: str
    reason: str


@dataclass
class CleanResult:
    source: str
    output_dir: str
    candidates: int
    auto_cleaned: int
    review: int
    changed_pixels: int
    changed_outside_authorized_mask: int
    integrity_ok: bool
    files: dict


def _read_rgb(path: Path) -> np.ndarray:
    with Image.open(path) as im:
        return np.asarray(im.convert("RGB"))


def _save_rgb(path: Path, arr: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(arr.astype(np.uint8), "RGB").save(path)


def _gray(rgb: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)


def _find_bright_regions(gray: np.ndarray) -> tuple[np.ndarray, list]:
    # Large near-white/bright regions are our conservative "bubble candidates".
    bright = cv2.inRange(gray, 238, 255)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    bright = cv2.morphologyEx(bright, cv2.MORPH_CLOSE, kernel, iterations=2)
    bright = cv2.morphologyEx(bright, cv2.MORPH_OPEN, kernel, iterations=1)

    n, labels, stats, _ = cv2.connectedComponentsWithStats(bright, 8)
    regions = []
    image_area = gray.shape[0] * gray.shape[1]
    min_area = max(1800, int(image_area * 0.001))

    for label in range(1, n):
        x, y, w, h, area = stats[label]
        if area < min_area or w < 45 or h < 28:
            continue
        regions.append((label, int(x), int(y), int(w), int(h), int(area)))
    return labels, regions


def _component_candidates(gray: np.ndarray, labels: np.ndarray, regions: list) -> tuple[np.ndarray, list[Candidate]]:
    # Dark ink-like components. We deliberately do NOT treat every dark pixel
    # as text; each component must be inside a safe bright region.
    dark = cv2.inRange(gray, 0, 175)
    dark = cv2.morphologyEx(
        dark, cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2)),
        iterations=1,
    )
    n, cc_labels, stats, _ = cv2.connectedComponentsWithStats(dark, 8)

    authorized = np.zeros_like(gray, dtype=np.uint8)
    candidates: list[Candidate] = []

    region_by_label = {r[0]: r for r in regions}

    for cid in range(1, n):
        x, y, w, h, area = [int(v) for v in stats[cid]]
        if area < 5 or area > 4500 or w < 2 or h < 3:
            continue

        cx = min(gray.shape[1] - 1, x + w // 2)
        cy = min(gray.shape[0] - 1, y + h // 2)
        bubble_label = int(labels[cy, cx])
        region = region_by_label.get(bubble_label)

        if not region:
            continue

        _, bx, by, bw, bh, barea = region
        clearance = min(x - bx, y - by, (bx + bw) - (x + w), (by + bh) - (y + h))

        # Reject components close to the detected bubble boundary. This is a
        # key protection against erasing balloon outlines / adjacent artwork.
        if clearance < 7:
            candidates.append(Candidate(
                x, y, w, h, area, barea, 0.0, 999.0, clearance, 0.0,
                "review", "componente próximo da borda da região segura"
            ))
            continue

        region_mask = labels == bubble_label
        vals = gray[region_mask]
        brightness = float(vals.mean()) if vals.size else 0.0
        texture = float(vals.std()) if vals.size else 999.0

        # Text-like geometry: broad enough to include letters but exclude
        # enormous illustration fragments.
        aspect = w / max(h, 1)
        geometry_ok = (h <= 90 and w <= 260 and 0.08 <= aspect <= 12.0)
        safe_background = brightness >= 242.0 and texture <= 24.0

        confidence = 0.0
        if safe_background:
            confidence += 0.50
        if clearance >= 12:
            confidence += 0.25
        if geometry_ok:
            confidence += 0.20
        if area <= 1800:
            confidence += 0.05

        if confidence >= 0.90:
            decision = "auto_clean"
            reason = "componente escuro contido em região clara, uniforme e afastada da borda"
            comp = (cc_labels == cid).astype(np.uint8) * 255
            # Slight dilation covers anti-aliased glyph edges, but remains
            # constrained to the interior of the bright region.
            comp = cv2.dilate(
                comp,
                cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)),
                iterations=1,
            )
            interior = region_mask.astype(np.uint8) * 255
            interior = cv2.erode(
                interior,
                cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)),
                iterations=1,
            )
            authorized = cv2.bitwise_or(authorized, cv2.bitwise_and(comp, interior))
        else:
            decision = "review"
            reason = "confiança insuficiente para limpeza automática"

        candidates.append(Candidate(
            x, y, w, h, area, barea, brightness, texture, clearance,
            round(confidence, 3), decision, reason
        ))

    return authorized, candidates


def _clean_with_local_background(rgb: np.ndarray, mask: np.ndarray) -> np.ndarray:
    # For the first experiment we use inpainting only inside the explicitly
    # authorized mask. It reconstructs from surrounding pixels and avoids
    # painting an arbitrary hard white rectangle.
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    cleaned = cv2.inpaint(bgr, mask, 3, cv2.INPAINT_TELEA)
    return cv2.cvtColor(cleaned, cv2.COLOR_BGR2RGB)


def _overlay(rgb: np.ndarray, mask: np.ndarray, candidates: list[Candidate]) -> np.ndarray:
    out = rgb.copy()
    # Authorized mask shown in green overlay; review boxes in yellow.
    tint = out.copy()
    tint[mask > 0] = (40, 220, 80)
    out = np.where((mask > 0)[..., None], (0.55 * out + 0.45 * tint).astype(np.uint8), out)

    bgr = cv2.cvtColor(out, cv2.COLOR_RGB2BGR)
    for c in candidates:
        if c.decision == "review":
            cv2.rectangle(bgr, (c.x, c.y), (c.x + c.w, c.y + c.h), (0, 210, 255), 1)
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)


def analyze_and_clean(source: Path, output_root: Path) -> CleanResult:
    source = Path(source)
    rgb = _read_rgb(source)
    gray = _gray(rgb)

    bubble_labels, regions = _find_bright_regions(gray)
    mask, candidates = _component_candidates(gray, bubble_labels, regions)
    cleaned = _clean_with_local_background(rgb, mask)
    overlay = _overlay(rgb, mask, candidates)

    stem_dir = output_root / source.stem
    stem_dir.mkdir(parents=True, exist_ok=True)

    mask_path = stem_dir / "authorized-mask.png"
    overlay_path = stem_dir / "overlay.png"
    cleaned_path = stem_dir / "cleaned-preview.png"
    report_path = stem_dir / "report.json"

    Image.fromarray(mask, "L").save(mask_path)
    _save_rgb(overlay_path, overlay)
    _save_rgb(cleaned_path, cleaned)

    changed = np.any(rgb != cleaned, axis=2)
    authorized = mask > 0
    outside = int(np.count_nonzero(changed & ~authorized))

    result = CleanResult(
        source=str(source),
        output_dir=str(stem_dir),
        candidates=len(candidates),
        auto_cleaned=sum(c.decision == "auto_clean" for c in candidates),
        review=sum(c.decision == "review" for c in candidates),
        changed_pixels=int(np.count_nonzero(changed)),
        changed_outside_authorized_mask=outside,
        integrity_ok=(outside == 0),
        files={
            "mask": str(mask_path),
            "overlay": str(overlay_path),
            "cleaned_preview": str(cleaned_path),
            "report": str(report_path),
        },
    )

    payload = {
        "schema_version": 1,
        "experiment": "bubble_cleaner_conservative_v1",
        "policy": {
            "source_immutable": True,
            "uncertain_action": "preserve",
            "auto_clean_only_inside_bright_low_texture_region": True,
            "post_check_no_change_outside_authorized_mask": True,
        },
        "result": asdict(result),
        "candidates": [asdict(c) for c in candidates],
    }
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def iter_images(path: Path) -> Iterable[Path]:
    if path.is_file():
        yield path
        return
    for ext in ("*.png", "*.jpg", "*.jpeg", "*.webp"):
        yield from sorted(path.glob(ext))


def main() -> int:
    parser = argparse.ArgumentParser(description="Experimental conservative speech-bubble cleaner")
    parser.add_argument("input", type=Path, help="Imagem ou pasta de imagens")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("bubble_cleaner_output"),
        help="Pasta de saída experimental",
    )
    args = parser.parse_args()

    images = list(iter_images(args.input))
    if not images:
        raise SystemExit("Nenhuma imagem encontrada.")

    print("EXPERIMENTO — LIMPEZA CONSERVADORA DE BALÕES")
    print("Originais NÃO serão alterados.")
    print()

    failures = 0
    for image in images:
        try:
            r = analyze_and_clean(image, args.output)
            status = "OK" if r.integrity_ok else "BLOQUEADO"
            print(
                f"[{status}] {image.name}: "
                f"{r.auto_cleaned} candidatos automáticos, "
                f"{r.review} para revisão, "
                f"{r.changed_outside_authorized_mask} pixels fora da máscara"
            )
        except Exception as exc:
            failures += 1
            print(f"[ERRO] {image}: {exc}")

    print()
    print(f"Saída: {args.output.resolve()}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
