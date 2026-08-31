#!/usr/bin/env python3
"""
Bubble Cleaner Experimental V2
Pipeline: balloon -> OCR text -> spatial agreement -> protected mask -> preview.

Safety rules:
- Never overwrites source images.
- No automatic cleaning unless OCR text is contained in a detected balloon.
- Balloon boundary is eroded before any mask can be authorized.
- Any ambiguous OCR region is preserved.
- Post-check verifies no changed pixel lies outside authorized mask.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np
from PIL import Image


@dataclass
class Balloon:
    id: int
    x: int
    y: int
    w: int
    h: int
    area: int
    contour_area: float
    fill_ratio: float
    brightness: float
    texture: float
    boundary_margin: int
    score: float


@dataclass
class OCRItem:
    text: str
    confidence: float
    polygon: list[list[int]]
    balloon_id: int | None
    containment: float
    decision: str
    reason: str


def read_rgb(path: Path) -> np.ndarray:
    with Image.open(path) as im:
        return np.asarray(im.convert("RGB"))


def save_rgb(path: Path, arr: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(arr.astype(np.uint8), "RGB").save(path)


def gray(rgb: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)


def contour_mask(shape: tuple[int, int], contour: np.ndarray) -> np.ndarray:
    m = np.zeros(shape, dtype=np.uint8)
    cv2.drawContours(m, [contour], -1, 255, thickness=-1)
    return m


def detect_balloons(rgb: np.ndarray) -> tuple[list[Balloon], dict[int, np.ndarray]]:
    """
    Conservative geometric detector for large, bright, closed regions.

    It intentionally prefers false negatives over treating arbitrary white
    illustration regions as speech balloons.
    """
    g = gray(rgb)
    h, w = g.shape
    image_area = h * w

    # Detect dark outlines, then seek enclosed bright interiors.
    edges = cv2.Canny(g, 40, 125)
    edges = cv2.dilate(
        edges,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)),
        iterations=1,
    )

    # Candidate bright regions.
    bright = cv2.inRange(g, 235, 255)
    bright = cv2.morphologyEx(
        bright,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)),
        iterations=2,
    )

    contours, _ = cv2.findContours(bright, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    balloons: list[Balloon] = []
    masks: dict[int, np.ndarray] = {}
    next_id = 1

    for c in contours:
        area = float(cv2.contourArea(c))
        if area < max(3500, image_area * 0.002):
            continue

        x, y, bw, bh = cv2.boundingRect(c)
        if bw < 70 or bh < 45:
            continue
        if bw > w * 0.95 and bh > h * 0.25:
            # Large page background, not a balloon.
            continue

        m = contour_mask(g.shape, c)
        vals = g[m > 0]
        if vals.size == 0:
            continue

        brightness = float(vals.mean())
        texture = float(vals.std())
        fill_ratio = area / max(1.0, float(bw * bh))

        # Require substantial bright interior, but allow speech tails.
        bright_ratio = float(np.mean(vals >= 235))
        if brightness < 238 or bright_ratio < 0.82:
            continue

        # Rounded/closed bubble-like region: neither a very thin strip nor
        # an almost-page-sized white panel.
        aspect = bw / max(1, bh)
        geometry_ok = 0.35 <= aspect <= 5.5 and fill_ratio >= 0.42
        if not geometry_ok:
            continue

        # Boundary evidence: look for edges in a thin band around contour.
        outline = cv2.morphologyEx(
            m, cv2.MORPH_GRADIENT,
            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        )
        outline_pixels = edges[outline > 0]
        edge_ratio = float(np.mean(outline_pixels > 0)) if outline_pixels.size else 0.0

        score = (
            0.35 * min(1.0, max(0.0, (brightness - 235) / 20))
            + 0.25 * min(1.0, bright_ratio)
            + 0.25 * min(1.0, edge_ratio / 0.25)
            + 0.15 * min(1.0, fill_ratio / 0.75)
        )

        # Extra conservatism: require some outline evidence.
        if edge_ratio < 0.05 or score < 0.58:
            continue

        boundary_margin = max(7, int(round(min(bw, bh) * 0.035)))
        interior = cv2.erode(
            m,
            cv2.getStructuringElement(
                cv2.MORPH_ELLIPSE,
                (boundary_margin * 2 + 1, boundary_margin * 2 + 1),
            ),
            iterations=1,
        )
        if np.count_nonzero(interior) < 1200:
            continue

        balloon = Balloon(
            id=next_id,
            x=int(x), y=int(y), w=int(bw), h=int(bh),
            area=int(np.count_nonzero(m)),
            contour_area=round(area, 2),
            fill_ratio=round(fill_ratio, 4),
            brightness=round(brightness, 2),
            texture=round(texture, 2),
            boundary_margin=boundary_margin,
            score=round(score, 3),
        )
        balloons.append(balloon)
        masks[next_id] = interior
        next_id += 1

    return balloons, masks


class EasyOCRBackend:
    """
    Stable experimental OCR backend. Model files are downloaded by EasyOCR on
    first use if not already cached.
    """
    def __init__(self, languages: list[str] | None = None):
        try:
            import easyocr
        except ImportError as exc:
            raise RuntimeError(
                "EasyOCR não está instalado. Instale requirements-v2.txt antes do teste."
            ) from exc

        self.reader = easyocr.Reader(languages or ["en"], gpu=False, verbose=False)

    def detect(self, rgb: np.ndarray) -> list[tuple[list[list[int]], str, float]]:
        result = self.reader.readtext(rgb, detail=1, paragraph=False)
        items = []
        for box, text, confidence in result:
            poly = [[int(round(p[0])), int(round(p[1]))] for p in box]
            items.append((poly, str(text), float(confidence)))
        return items


def polygon_mask(shape: tuple[int, int], polygon: list[list[int]], expand: int = 2) -> np.ndarray:
    m = np.zeros(shape, dtype=np.uint8)
    pts = np.asarray(polygon, dtype=np.int32)
    cv2.fillPoly(m, [pts], 255)
    if expand > 0:
        m = cv2.dilate(
            m,
            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (expand * 2 + 1, expand * 2 + 1)),
            iterations=1,
        )
    return m


def containment_ratio(text_mask: np.ndarray, balloon_mask: np.ndarray) -> float:
    total = np.count_nonzero(text_mask)
    if total == 0:
        return 0.0
    inside = np.count_nonzero((text_mask > 0) & (balloon_mask > 0))
    return float(inside / total)


def build_authorized_mask(
    rgb: np.ndarray,
    balloons: list[Balloon],
    balloon_masks: dict[int, np.ndarray],
    ocr_raw: list[tuple[list[list[int]], str, float]],
    min_ocr_conf: float = 0.55,
    min_containment: float = 0.94,
) -> tuple[np.ndarray, list[OCRItem]]:
    shape = rgb.shape[:2]
    authorized = np.zeros(shape, dtype=np.uint8)
    decisions: list[OCRItem] = []

    for polygon, text, confidence in ocr_raw:
        tmask = polygon_mask(shape, polygon, expand=2)

        best_id = None
        best_ratio = 0.0
        for balloon in balloons:
            ratio = containment_ratio(tmask, balloon_masks[balloon.id])
            if ratio > best_ratio:
                best_ratio = ratio
                best_id = balloon.id

        if confidence < min_ocr_conf:
            decision = "preserve"
            reason = "OCR com confiança insuficiente"
        elif best_id is None or best_ratio < min_containment:
            decision = "preserve"
            reason = "texto não está suficientemente contido em balão confirmado"
        else:
            decision = "auto_clean"
            reason = "OCR e detector de balão concordam espacialmente"
            safe = cv2.bitwise_and(tmask, balloon_masks[best_id])
            authorized = cv2.bitwise_or(authorized, safe)

        decisions.append(OCRItem(
            text=text,
            confidence=round(confidence, 4),
            polygon=polygon,
            balloon_id=best_id,
            containment=round(best_ratio, 4),
            decision=decision,
            reason=reason,
        ))

    return authorized, decisions


def clean(rgb: np.ndarray, mask: np.ndarray) -> np.ndarray:
    if not np.any(mask):
        return rgb.copy()
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    result = cv2.inpaint(bgr, mask, 3, cv2.INPAINT_TELEA)
    return cv2.cvtColor(result, cv2.COLOR_BGR2RGB)


def make_overlay(
    rgb: np.ndarray,
    balloons: list[Balloon],
    balloon_masks: dict[int, np.ndarray],
    decisions: list[OCRItem],
    authorized_mask: np.ndarray,
) -> np.ndarray:
    out = rgb.copy()
    bgr = cv2.cvtColor(out, cv2.COLOR_RGB2BGR)

    # Blue: detected balloon.
    for b in balloons:
        cv2.rectangle(bgr, (b.x, b.y), (b.x + b.w, b.y + b.h), (255, 100, 40), 2)
        cv2.putText(
            bgr, f"B{b.id} {b.score:.2f}",
            (b.x, max(16, b.y - 5)),
            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 100, 40), 1, cv2.LINE_AA,
        )

    # Green: authorized OCR; yellow: preserved OCR.
    for item in decisions:
        pts = np.asarray(item.polygon, dtype=np.int32).reshape((-1, 1, 2))
        color = (60, 210, 60) if item.decision == "auto_clean" else (0, 210, 255)
        cv2.polylines(bgr, [pts], True, color, 2)

    out = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)

    if np.any(authorized_mask):
        tint = out.copy()
        tint[authorized_mask > 0] = (40, 220, 80)
        out = np.where(
            (authorized_mask > 0)[..., None],
            (0.60 * out + 0.40 * tint).astype(np.uint8),
            out,
        )
    return out


def process_image(source: Path, output_root: Path, languages: list[str]) -> dict:
    source = Path(source)
    rgb = read_rgb(source)
    original_bytes = source.read_bytes()

    balloons, balloon_masks = detect_balloons(rgb)
    ocr = EasyOCRBackend(languages)
    ocr_raw = ocr.detect(rgb)

    authorized, decisions = build_authorized_mask(
        rgb, balloons, balloon_masks, ocr_raw
    )
    cleaned = clean(rgb, authorized)

    # Integrity gate: inpainting must not alter pixels outside authorized mask.
    changed = np.any(rgb != cleaned, axis=2)
    outside = int(np.count_nonzero(changed & ~(authorized > 0)))
    integrity_ok = outside == 0

    # If integrity gate fails, do not expose an altered preview as valid.
    if not integrity_ok:
        cleaned = rgb.copy()

    overlay = make_overlay(rgb, balloons, balloon_masks, decisions, authorized)

    out_dir = output_root / source.stem
    out_dir.mkdir(parents=True, exist_ok=True)

    mask_path = out_dir / "authorized-mask.png"
    overlay_path = out_dir / "overlay.png"
    preview_path = out_dir / "cleaned-preview.png"
    report_path = out_dir / "report.json"

    Image.fromarray(authorized, "L").save(mask_path)
    save_rgb(overlay_path, overlay)
    save_rgb(preview_path, cleaned)

    # Source immutability check.
    source_unchanged = source.read_bytes() == original_bytes

    payload = {
        "schema_version": 2,
        "experiment": "bubble_cleaner_v2_balloon_ocr_double_check",
        "source": str(source),
        "policy": {
            "source_immutable": True,
            "balloon_must_be_confirmed": True,
            "ocr_must_be_confirmed": True,
            "min_ocr_confidence": 0.55,
            "min_text_containment_in_eroded_balloon": 0.94,
            "uncertain_action": "preserve",
            "post_check_no_change_outside_authorized_mask": True,
        },
        "summary": {
            "balloons_detected": len(balloons),
            "ocr_regions": len(decisions),
            "auto_clean": sum(d.decision == "auto_clean" for d in decisions),
            "preserved": sum(d.decision != "auto_clean" for d in decisions),
            "authorized_pixels": int(np.count_nonzero(authorized)),
            "changed_pixels": int(np.count_nonzero(changed)),
            "changed_outside_authorized_mask": outside,
            "integrity_ok": integrity_ok,
            "source_unchanged": source_unchanged,
        },
        "balloons": [asdict(b) for b in balloons],
        "ocr": [asdict(d) for d in decisions],
        "files": {
            "authorized_mask": str(mask_path),
            "overlay": str(overlay_path),
            "cleaned_preview": str(preview_path),
            "report": str(report_path),
        },
    }

    report_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return payload


def iter_images(path: Path) -> Iterable[Path]:
    if path.is_file():
        yield path
        return
    for pattern in ("*.png", "*.jpg", "*.jpeg", "*.webp"):
        yield from sorted(path.glob(pattern))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Experimental V2: balloon + OCR double-check cleaner"
    )
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, default=Path("bubble_cleaner_v2_output"))
    parser.add_argument("--languages", default="en")
    args = parser.parse_args()

    images = list(iter_images(args.input))
    if not images:
        raise SystemExit("Nenhuma imagem encontrada.")

    languages = [x.strip() for x in args.languages.split(",") if x.strip()]

    print("BUBBLE CLEANER V2 — DUPLA CHECAGEM")
    print("Originais NÃO serão alterados.")
    print()

    failures = 0
    for source in images:
        try:
            r = process_image(source, args.output, languages)
            s = r["summary"]
            status = "OK" if s["integrity_ok"] and s["source_unchanged"] else "BLOQUEADO"
            print(
                f"[{status}] {source.name}: "
                f"{s['balloons_detected']} balão(ões), "
                f"{s['ocr_regions']} OCR, "
                f"{s['auto_clean']} autorizado(s), "
                f"{s['preserved']} preservado(s), "
                f"{s['changed_outside_authorized_mask']} px fora da máscara"
            )
        except Exception as exc:
            failures += 1
            print(f"[ERRO] {source.name}: {exc}")

    print()
    print(f"Saída: {args.output.resolve()}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
