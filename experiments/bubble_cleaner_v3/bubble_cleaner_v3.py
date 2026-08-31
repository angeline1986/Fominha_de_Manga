#!/usr/bin/env python3
"""
Bubble Cleaner Experimental V3.5

Keeps V3.2 detector/OCR/mask architecture intact.
Changes only the fill strategy used after an authorized mask exists.

Strategy:
- Estimate whether the authorized region belongs to a bright, low-variance balloon background.
- If yes, fill only authorized pixels using a robust local background estimate.
- If not, fall back to OpenCV Telea inpainting.
- Regardless of strategy, only authorized pixels are copied to the output.
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

HF_REPO = "Kiuyha/Manga-Bubble-YOLO"
HF_MODEL_FILE = "weights/yolo26n.pt"
MODEL_SHA256 = "29dbed070efdfa9b2b9f0b6a393bd9d02b86876ab54976fdf0a5cbd28b5c4334"


@dataclass
class Detection:
    id: int
    x1: int
    y1: int
    x2: int
    y2: int
    confidence: float
    class_id: int
    class_name: str
    background_brightness: float
    background_texture: float
    gate_ok: bool
    gate_reason: str


@dataclass
class OCRDecision:
    text: str
    confidence: float
    polygon: list[list[int]]
    detection_id: int | None
    containment: float
    decision: str
    reason: str


def sha256_file(path: Path) -> str:
    import hashlib
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def resolve_model(model_path: Path | None = None) -> Path:
    if model_path:
        p = Path(model_path).expanduser().resolve()
        if not p.exists():
            raise RuntimeError(f"Modelo não encontrado: {p}")
        return p

    try:
        from huggingface_hub import hf_hub_download
    except ImportError as exc:
        raise RuntimeError("huggingface_hub não está instalado.") from exc

    print(f"[MODELO] Obtendo {HF_REPO}/{HF_MODEL_FILE}...")
    downloaded = Path(hf_hub_download(repo_id=HF_REPO, filename=HF_MODEL_FILE))
    digest = sha256_file(downloaded)
    if digest != MODEL_SHA256:
        raise RuntimeError(
            "SHA256 inesperado para o modelo baixado. "
            f"Esperado {MODEL_SHA256}, obtido {digest}."
        )
    print("[MODELO] SHA256 validado.")
    return downloaded


def read_rgb(path: Path) -> np.ndarray:
    with Image.open(path) as im:
        return np.asarray(im.convert("RGB"))


def save_rgb(path: Path, arr: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(arr.astype(np.uint8), "RGB").save(path)


def detect_regions(rgb: np.ndarray, model_path: Path, conf: float = 0.55) -> list[Detection]:
    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise RuntimeError("ultralytics não está instalado.") from exc

    model = YOLO(str(model_path))
    results = model.predict(source=rgb, conf=conf, imgsz=1280, verbose=False, device="cpu")
    if not results:
        return []

    result = results[0]
    names = result.names or {}
    detections: list[Detection] = []
    boxes = getattr(result, "boxes", None)
    if boxes is None:
        return []

    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    h, w = gray.shape

    for idx, box in enumerate(boxes, start=1):
        xyxy = box.xyxy[0].detach().cpu().numpy().tolist()
        x1, y1, x2, y2 = [int(round(v)) for v in xyxy]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        if x2 <= x1 or y2 <= y1:
            continue

        confidence = float(box.conf[0].detach().cpu().item())
        class_id = int(box.cls[0].detach().cpu().item())
        class_name = str(names.get(class_id, class_id))
        roi = gray[y1:y2, x1:x2]
        brightness = float(roi.mean()) if roi.size else 0.0
        texture = float(roi.std()) if roi.size else 999.0
        bright_ratio = float(np.mean(roi >= 225)) if roi.size else 0.0

        # V3.5: conservative guard against bright, unusually low-texture
        # graphic/SFX regions that the specialized detector may label as text.
        # This is intentionally a combined condition rather than a texture-only
        # cutoff, preserving normal bright dialogue balloons.
        sfx_like_low_texture = (
            brightness >= 225
            and texture < 50
        )

        gate_ok = (
            confidence >= conf
            and roi.size > 0
            and bright_ratio >= 0.55
            and brightness >= 205
            and not sfx_like_low_texture
        )
        if gate_ok:
            reason = "detector especializado + gate visual aprovados"
        elif sfx_like_low_texture:
            reason = (
                "preservado pelo gate V3.5: região muito clara e de baixa textura, "
                "compatível com texto gráfico/SFX sem balão "
                f"(brilho={brightness:.1f}, textura={texture:.1f})"
            )
        else:
            reason = (
                "região especializada detectada, mas gate visual rejeitou "
                f"(brilho={brightness:.1f}, bright_ratio={bright_ratio:.2f})"
            )

        detections.append(Detection(
            id=idx, x1=x1, y1=y1, x2=x2, y2=y2,
            confidence=round(confidence, 4),
            class_id=class_id, class_name=class_name,
            background_brightness=round(brightness, 2),
            background_texture=round(texture, 2),
            gate_ok=gate_ok, gate_reason=reason,
        ))
    return detections


class EasyOCRBackend:
    def __init__(self, languages: list[str]):
        try:
            import easyocr
        except ImportError as exc:
            raise RuntimeError("EasyOCR não está instalado.") from exc
        self.reader = easyocr.Reader(languages, gpu=False, verbose=False)

    def detect(self, rgb: np.ndarray):
        raw = self.reader.readtext(rgb, detail=1, paragraph=False)
        out = []
        for box, text, confidence in raw:
            poly = [[int(round(p[0])), int(round(p[1]))] for p in box]
            out.append((poly, str(text), float(confidence)))
        return out


def polygon_mask(shape: tuple[int, int], polygon: list[list[int]], expand: int = 2) -> np.ndarray:
    mask = np.zeros(shape, dtype=np.uint8)
    pts = np.asarray(polygon, dtype=np.int32)
    cv2.fillPoly(mask, [pts], 255)
    if expand:
        mask = cv2.dilate(
            mask,
            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (expand * 2 + 1, expand * 2 + 1)),
            iterations=1,
        )
    return mask


def detection_box_mask(shape: tuple[int, int], d: Detection) -> np.ndarray:
    m = np.zeros(shape, dtype=np.uint8)
    cv2.rectangle(m, (d.x1, d.y1), (d.x2, d.y2), 255, thickness=-1)
    return m


def protected_detection_mask(shape: tuple[int, int], d: Detection) -> np.ndarray:
    m = np.zeros(shape, dtype=np.uint8)
    width = d.x2 - d.x1
    height = d.y2 - d.y1
    margin = max(4, int(round(min(width, height) * 0.025)))
    x1, y1 = d.x1 + margin, d.y1 + margin
    x2, y2 = d.x2 - margin, d.y2 - margin
    if x2 > x1 and y2 > y1:
        cv2.rectangle(m, (x1, y1), (x2, y2), 255, thickness=-1)
    return m


def containment(text_mask: np.ndarray, region_mask: np.ndarray) -> float:
    total = int(np.count_nonzero(text_mask))
    if not total:
        return 0.0
    return float(np.count_nonzero((text_mask > 0) & (region_mask > 0)) / total)


def polygon_center(polygon: list[list[int]]) -> tuple[float, float]:
    pts = np.asarray(polygon, dtype=np.float32)
    return float(pts[:, 0].mean()), float(pts[:, 1].mean())


def point_inside_detection(center: tuple[float, float], d: Detection) -> bool:
    x, y = center
    return d.x1 <= x <= d.x2 and d.y1 <= y <= d.y2


def expand_text_mask(
    rgb: np.ndarray,
    seed_mask: np.ndarray,
    protected_mask: np.ndarray,
    *,
    dark_threshold: int = 185,
    proximity_px: int = 12,
    max_component_area: int = 2200,
    max_component_width: int = 180,
    max_component_height: int = 90,
) -> np.ndarray:
    if not np.any(seed_mask):
        return seed_mask.copy()

    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    candidates = np.zeros_like(seed_mask)
    candidates[(gray <= dark_threshold) & (protected_mask > 0)] = 255

    kernel_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    candidates = cv2.morphologyEx(candidates, cv2.MORPH_CLOSE, kernel_close)

    near_seed = cv2.dilate(
        seed_mask,
        cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (proximity_px * 2 + 1, proximity_px * 2 + 1)
        ),
        iterations=1,
    )

    n, labels, stats, _ = cv2.connectedComponentsWithStats(
        (candidates > 0).astype(np.uint8), connectivity=8
    )
    expanded = seed_mask.copy()

    for label in range(1, n):
        x, y, w, h, area = stats[label].tolist()
        if area <= 0:
            continue
        if area > max_component_area or w > max_component_width or h > max_component_height:
            continue
        comp = labels == label
        if not np.any(comp & (near_seed > 0)):
            continue
        if np.any(comp & ~(protected_mask > 0)):
            continue
        expanded[comp] = 255

    expanded = cv2.dilate(
        expanded,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)),
        iterations=1,
    )
    expanded = cv2.bitwise_and(expanded, protected_mask)
    return expanded


def authorize(
    rgb: np.ndarray,
    detections: list[Detection],
    ocr_items,
    min_ocr_conf: float = 0.60,
    min_association_containment: float = 0.80,
) -> tuple[np.ndarray, list[OCRDecision]]:
    shape = rgb.shape[:2]
    approved = [d for d in detections if d.gate_ok]
    association_masks = {d.id: detection_box_mask(shape, d) for d in approved}
    protected_masks = {d.id: protected_detection_mask(shape, d) for d in approved}
    seeds_by_detection = {d.id: np.zeros(shape, dtype=np.uint8) for d in approved}
    decisions: list[OCRDecision] = []

    for polygon, text, ocr_conf in ocr_items:
        tmask = polygon_mask(shape, polygon, expand=2)
        center = polygon_center(polygon)
        best_detection: Detection | None = None
        best_containment = 0.0

        for d in approved:
            ratio = containment(tmask, association_masks[d.id])
            center_inside = point_inside_detection(center, d)
            if center_inside and ratio >= min_association_containment and ratio > best_containment:
                best_detection = d
                best_containment = ratio

        if ocr_conf < min_ocr_conf:
            decision = "preserve"
            reason = "OCR abaixo da confiança mínima"
            detection_id = best_detection.id if best_detection else None
        elif best_detection is None:
            decision = "preserve"
            reason = "OCR não associado a balão confirmado"
            detection_id = None
        else:
            detection_id = best_detection.id
            clipped = cv2.bitwise_and(tmask, protected_masks[detection_id])
            if not np.any(clipped):
                decision = "preserve"
                reason = "OCR associado, mas sem pixels dentro da área interna protegida"
            else:
                decision = "auto_clean"
                reason = (
                    "OCR agrupado no mesmo balão confirmado; "
                    "máscara complementada apenas por componentes tipográficos adjacentes"
                )
                seeds_by_detection[detection_id] = cv2.bitwise_or(
                    seeds_by_detection[detection_id], clipped
                )

        decisions.append(OCRDecision(
            text=text,
            confidence=round(ocr_conf, 4),
            polygon=polygon,
            detection_id=detection_id,
            containment=round(best_containment, 4),
            decision=decision,
            reason=reason,
        ))

    authorized = np.zeros(shape, dtype=np.uint8)
    for d in approved:
        seed = seeds_by_detection[d.id]
        if not np.any(seed):
            continue
        completed = expand_text_mask(rgb, seed, protected_masks[d.id])
        authorized = cv2.bitwise_or(authorized, completed)

    return authorized, decisions


def _ring_around_mask(mask: np.ndarray, radius: int = 10) -> np.ndarray:
    kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE, (radius * 2 + 1, radius * 2 + 1)
    )
    dilated = cv2.dilate(mask, kernel, iterations=1)
    return ((dilated > 0) & ~(mask > 0)).astype(np.uint8)


def _robust_local_background(rgb: np.ndarray, mask: np.ndarray) -> tuple[np.ndarray | None, dict]:
    ring = _ring_around_mask(mask, radius=10)
    pixels = rgb[ring > 0]

    if pixels.size == 0:
        return None, {"usable": False, "reason": "anel local vazio"}

    # Prefer bright ring pixels to avoid sampling text edges or balloon outlines.
    bright = pixels[np.mean(pixels, axis=1) >= 210]
    sample = bright if len(bright) >= max(50, len(pixels) * 0.35) else pixels

    median = np.median(sample, axis=0)
    luminance = np.mean(sample, axis=1)
    lum_median = float(np.median(luminance))
    lum_std = float(np.std(luminance))
    channel_spread = float(np.max(median) - np.min(median))

    usable = (
        lum_median >= 220
        and lum_std <= 18
        and channel_spread <= 18
    )

    return median.astype(np.uint8), {
        "usable": bool(usable),
        "ring_pixels": int(len(pixels)),
        "sample_pixels": int(len(sample)),
        "luminance_median": round(lum_median, 2),
        "luminance_std": round(lum_std, 2),
        "median_rgb": [int(x) for x in median],
        "channel_spread": round(channel_spread, 2),
        "reason": "fundo claro e uniforme" if usable else "fundo não uniforme o bastante",
    }


def clean(rgb: np.ndarray, mask: np.ndarray) -> tuple[np.ndarray, dict]:
    if not np.any(mask):
        return rgb.copy(), {"strategy": "none", "reason": "máscara vazia"}

    local_color, diagnostics = _robust_local_background(rgb, mask)

    if local_color is not None and diagnostics.get("usable"):
        cleaned = rgb.copy()

        # V3.4: when the local background is confirmed bright and uniform,
        # replace every authorized pixel directly with the robust local color.
        # Do not feather with original pixels: that could reintroduce glyph residue.
        cleaned[mask > 0] = local_color
        return cleaned, {
            "strategy": "uniform_local_background_direct_fill",
            **diagnostics,
        }

    # Fallback for non-uniform balloon interiors.
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    inpainted_bgr = cv2.inpaint(bgr, mask, 3, cv2.INPAINT_TELEA)
    inpainted_rgb = cv2.cvtColor(inpainted_bgr, cv2.COLOR_BGR2RGB)

    cleaned = rgb.copy()
    cleaned[mask > 0] = inpainted_rgb[mask > 0]

    return cleaned, {
        "strategy": "telea_fallback",
        **diagnostics,
    }


def overlay_image(
    rgb: np.ndarray,
    detections: list[Detection],
    decisions: list[OCRDecision],
    authorized: np.ndarray,
) -> np.ndarray:
    bgr = cv2.cvtColor(rgb.copy(), cv2.COLOR_RGB2BGR)

    for d in detections:
        color = (255, 100, 40) if d.gate_ok else (220, 40, 220)
        cv2.rectangle(bgr, (d.x1, d.y1), (d.x2, d.y2), color, 2)
        cv2.putText(
            bgr, f"D{d.id} {d.confidence:.2f}",
            (d.x1, max(18, d.y1 - 5)),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA,
        )

    for item in decisions:
        pts = np.asarray(item.polygon, dtype=np.int32).reshape((-1, 1, 2))
        color = (60, 210, 60) if item.decision == "auto_clean" else (0, 210, 255)
        cv2.polylines(bgr, [pts], True, color, 2)

    out = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    if np.any(authorized):
        tint = out.copy()
        tint[authorized > 0] = (40, 220, 80)
        out = np.where(
            (authorized > 0)[..., None],
            (0.60 * out + 0.40 * tint).astype(np.uint8),
            out,
        )
    return out


def process_image(
    source: Path,
    output_root: Path,
    model_path: Path,
    languages: list[str],
    detector_conf: float,
) -> dict:
    source = Path(source)
    original_bytes = source.read_bytes()
    rgb = read_rgb(source)

    detections = detect_regions(rgb, model_path, conf=detector_conf)
    ocr = EasyOCRBackend(languages)
    ocr_items = ocr.detect(rgb)
    authorized, decisions = authorize(rgb, detections, ocr_items)
    cleaned, fill_info = clean(rgb, authorized)

    changed = np.any(rgb != cleaned, axis=2)
    outside = int(np.count_nonzero(changed & ~(authorized > 0)))
    source_unchanged = source.read_bytes() == original_bytes
    integrity_ok = outside == 0 and source_unchanged

    if not integrity_ok:
        cleaned = rgb.copy()

    overlay = overlay_image(rgb, detections, decisions, authorized)

    out_dir = output_root / source.stem
    out_dir.mkdir(parents=True, exist_ok=True)
    mask_path = out_dir / "authorized-mask.png"
    overlay_path = out_dir / "overlay.png"
    preview_path = out_dir / "cleaned-preview.png"
    report_path = out_dir / "report.json"

    Image.fromarray(authorized, "L").save(mask_path)
    save_rgb(overlay_path, overlay)
    save_rgb(preview_path, cleaned)

    payload = {
        "schema_version": 35,
        "experiment": "bubble_cleaner_v3_5_sfx_gate_guard",
        "source": str(source),
        "model": {
            "repo": HF_REPO,
            "file": HF_MODEL_FILE,
            "sha256": MODEL_SHA256,
            "resolved_path": str(model_path),
        },
        "policy": {
            "source_immutable": True,
            "specialized_detector_required": True,
            "visual_gate_required": True,
            "sfx_low_texture_guard": {
                "min_brightness": 225,
                "max_texture_exclusive": 50
            },
            "ocr_required": True,
            "min_ocr_confidence": 0.60,
            "min_association_containment": 0.80,
            "ocr_grouping_by_confirmed_detection": True,
            "mask_completion": "nearby_dark_connected_components_only",
            "adaptive_fill": True,
            "uniform_background_fill_if_safe": True,
            "telea_fallback": True,
            "uncertain_action": "preserve",
            "post_check_no_change_outside_authorized_mask": True,
        },
        "fill": fill_info,
        "summary": {
            "specialized_detections": len(detections),
            "visual_gate_approved": sum(d.gate_ok for d in detections),
            "ocr_regions": len(decisions),
            "auto_clean": sum(d.decision == "auto_clean" for d in decisions),
            "preserved": sum(d.decision != "auto_clean" for d in decisions),
            "authorized_pixels": int(np.count_nonzero(authorized)),
            "changed_pixels": int(np.count_nonzero(changed)),
            "changed_outside_authorized_mask": outside,
            "source_unchanged": source_unchanged,
            "integrity_ok": integrity_ok,
        },
        "detections": [asdict(d) for d in detections],
        "ocr": [asdict(d) for d in decisions],
        "files": {
            "authorized_mask": str(mask_path),
            "overlay": str(overlay_path),
            "cleaned_preview": str(preview_path),
            "report": str(report_path),
        },
    }
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def iter_images(path: Path) -> Iterable[Path]:
    if path.is_file():
        yield path
        return
    for pattern in ("*.png", "*.jpg", "*.jpeg", "*.webp"):
        yield from sorted(path.glob(pattern))


def main() -> int:
    parser = argparse.ArgumentParser(description="Bubble Cleaner Experimental V3.5")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, default=Path("bubble_cleaner_output/v3"))
    parser.add_argument("--languages", default="en")
    parser.add_argument("--detector-conf", type=float, default=0.55)
    parser.add_argument("--model", type=Path, default=None)
    args = parser.parse_args()

    images = list(iter_images(args.input))
    if not images:
        raise SystemExit("Nenhuma imagem encontrada.")

    model_path = resolve_model(args.model)
    languages = [x.strip() for x in args.languages.split(",") if x.strip()]

    print("BUBBLE CLEANER V3.5 — GATE CONSERVADOR PARA TEXTO GRÁFICO/SFX")
    print("Originais NÃO serão alterados.")
    print()

    failures = 0
    for source in images:
        try:
            payload = process_image(
                source, args.output, model_path, languages, args.detector_conf
            )
            s = payload["summary"]
            fill = payload["fill"]
            status = "OK" if s["integrity_ok"] else "BLOQUEADO"
            print(
                f"[{status}] {source.name}: "
                f"{s['specialized_detections']} detecção(ões), "
                f"{s['visual_gate_approved']} gate aprovado, "
                f"{s['ocr_regions']} OCR, "
                f"{s['auto_clean']} autorizado(s), "
                f"{s['preserved']} preservado(s), "
                f"{s['authorized_pixels']} px autorizados, "
                f"fill={fill.get('strategy')}, "
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
