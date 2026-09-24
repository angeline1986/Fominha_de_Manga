from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

import cv2
import numpy as np

from processamento.limpeza_baloes import patch_balao_transparente_experimento as transparent
from processamento.limpeza_baloes import patch_degrade_experimento as base


ALGORITHM = "textoff_special_roi_transparent_legacy_v1"


def _normalize_selections(selections, width: int, height: int) -> list[dict]:
    if isinstance(selections, dict):
        selections = [selections]
    if not isinstance(selections, list) or not selections:
        raise ValueError("Selecione pelo menos uma região para aplicar Balão Transparente — Legado.")

    normalized = []
    for index, item in enumerate(selections, start=1):
        if not isinstance(item, dict):
            raise ValueError("Seleção do Balão Transparente — Legado inválida.")
        try:
            x = int(round(float(item["x"])))
            y = int(round(float(item["y"])))
            w = int(round(float(item["width"])))
            h = int(round(float(item["height"])))
        except Exception as exc:
            raise ValueError("Seleção do Balão Transparente — Legado inválida.") from exc
        if w <= 0 or h <= 0:
            raise ValueError("Seleção do Balão Transparente — Legado possui área vazia.")
        x1, y1 = max(0, x), max(0, y)
        x2, y2 = min(width, x + w), min(height, y + h)
        if x2 <= x1 or y2 <= y1:
            raise ValueError("Seleção do Balão Transparente — Legado está fora da imagem.")
        normalized.append({"index": index, "x": x1, "y": y1, "width": x2 - x1, "height": y2 - y1})
    return normalized


def _intersects(bbox, roi: dict) -> bool:
    x, y, w, h = bbox
    rx, ry, rw, rh = roi["x"], roi["y"], roi["width"], roi["height"]
    return x < rx + rw and x + w > rx and y < ry + rh and y + h > ry


def _cleaner_mask(source: Path, target: Path) -> np.ndarray:
    cleaner_target = target / "cleaner_stage"
    if cleaner_target.exists():
        shutil.rmtree(cleaner_target)
    cleaner_target.mkdir(parents=True, exist_ok=True)

    _, mask_path = base._run_cleaner(source, cleaner_target)
    mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
    if mask is None:
        raise RuntimeError(f"Falha ao ler máscara do Cleaner: {mask_path}")
    return mask


def run_transparent_legacy_roi(source: Path, target: Path, selections) -> tuple[Path, dict]:
    """Variante histórica: Cleaner -> ROI -> 3x3 -> 9x9 -> LaMa.

    Não chama Balloon Authorization. O patch Transparente protegido permanece intacto.
    A promoção oficial fica bloqueada durante a prova A/B.
    """
    started = time.monotonic()
    target.mkdir(parents=True, exist_ok=True)

    original = transparent._read_image(source)
    height, width = original.shape[:2]
    rois = _normalize_selections(selections, width, height)

    cleaner_mask = _cleaner_mask(source, target)
    if cleaner_mask.shape != original.shape[:2]:
        raise RuntimeError(
            "Dimensões divergentes entre imagem e máscara do Cleaner: "
            f"image={original.shape[:2]} mask={cleaner_mask.shape}"
        )

    binary = (cleaner_mask > 0).astype(np.uint8)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    restricted_cleaner = np.zeros_like(cleaner_mask)
    selected_components = []
    all_components = []

    for label in range(1, count):
        x, y, w, h, area = map(int, stats[label])
        hits = [roi["index"] for roi in rois if _intersects((x, y, w, h), roi)]
        row = {"label": label, "bbox": [x, y, w, h], "area": area, "roi_hits": hits}
        all_components.append(row)
        if hits:
            restricted_cleaner[labels == label] = cleaner_mask[labels == label]
            selected_components.append(row)

    if not selected_components:
        raise RuntimeError("Nenhum componente do Cleaner intersecta as regiões selecionadas.")

    kernel_3x3 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, transparent.BASE_DILATION)
    base_mask = cv2.dilate(restricted_cleaner, kernel_3x3, iterations=1)
    authorized_mask = transparent._authorize_mask(base_mask)

    cleaner_pixels = int(np.count_nonzero(restricted_cleaner))
    base_pixels = int(np.count_nonzero(base_mask))
    authorized_pixels = int(np.count_nonzero(authorized_mask))
    if authorized_pixels == 0:
        raise RuntimeError("Máscara vazia após dilatações históricas 3x3 e 9x9.")

    cleaner_path = target / "00_cleaner_mask_roi.png"
    base_path = target / "01_text_mask_3x3_roi.png"
    authorized_path = target / "02_authorized_mask_9x9_roi.png"
    overlay_path = target / "03_authorized_mask_overlay_roi.png"
    result_path = target / "04_lama_text_only_legacy_roi.png"
    lama_meta_path = target / "lama_metadata_legacy_roi.json"

    for path, image in (
        (cleaner_path, restricted_cleaner),
        (base_path, base_mask),
        (authorized_path, authorized_mask),
    ):
        if not cv2.imwrite(str(path), image):
            raise RuntimeError(f"Falha ao gravar {path}")

    transparent._write_mask_overlay(original, authorized_mask, overlay_path)
    transparent._run_lama_worker(source, authorized_path, result_path, lama_meta_path)

    technical = cv2.imread(str(result_path))
    if technical is None or technical.shape != original.shape:
        raise RuntimeError("Resultado técnico do LaMa inválido.")

    changed = np.any(technical != original, axis=2)
    outside = changed & ~(authorized_mask > 0)
    outside_count = int(np.count_nonzero(outside))
    if outside_count:
        raise RuntimeError(
            f"Falha de segurança: {outside_count} pixel(s) alterado(s) fora da máscara Legado."
        )

    lama_meta = json.loads(lama_meta_path.read_text(encoding="utf-8"))
    meta = {
        "algorithm": ALGORITHM,
        "proof_phase": True,
        "promotion_allowed": False,
        "variant": "legacy_pre_balloon_authorization",
        "balloon_authorization_used": False,
        "selection_count": len(rois),
        "selections": rois,
        "selection_rule": "raw_cleaner_components_intersecting_roi",
        "cleaner_mask_pixels_after_roi": cleaner_pixels,
        "base_mask_pixels_after_roi_3x3": base_pixels,
        "authorized_mask_pixels_after_roi_9x9": authorized_pixels,
        "components_before_count": len(all_components),
        "components_selected_count": len(selected_components),
        "selected_components": selected_components,
        "base_dilation": list(transparent.BASE_DILATION),
        "authorized_dilation": list(transparent.AUTHORIZED_DILATION),
        "lama_padding": transparent.LAMA_PADDING,
        "lama": lama_meta,
        "composition_mode": "technical_result_from_source_legacy",
        "effective_changed_pixels": int(np.count_nonzero(changed)),
        "technical_changed_outside_authorized_pixels": outside_count,
        "base_snapshot_used": False,
        "preview_result": result_path.name,
        "promotion_result": result_path.name,
        "protected_patch_modified": False,
        "artifacts": {
            "restricted_cleaner_mask": cleaner_path.name,
            "text_mask_3x3": base_path.name,
            "authorized_mask_9x9": authorized_path.name,
            "overlay": overlay_path.name,
            "technical_result": result_path.name,
            "preview_result": result_path.name,
        },
        "elapsed_seconds": round(time.monotonic() - started, 3),
    }
    (target / "roi_report.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return result_path, meta
