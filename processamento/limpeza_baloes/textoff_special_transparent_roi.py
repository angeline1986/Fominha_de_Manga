from __future__ import annotations

import json
import time
from pathlib import Path

import cv2
import numpy as np

from processamento.limpeza_baloes import patch_balao_transparente_experimento as transparent

ALGORITHM = "textoff_special_roi_transparent_v1"

def _normalize_selections(selections, width: int, height: int) -> list[dict]:
    if isinstance(selections, dict):
        selections = [selections]
    if not isinstance(selections, list) or not selections:
        raise ValueError("Selecione pelo menos uma região para aplicar o Patch Balão Transparente.")
    normalized = []
    for index, item in enumerate(selections, start=1):
        if not isinstance(item, dict):
            raise ValueError("Seleção do Patch Balão Transparente inválida.")
        try:
            x = int(round(float(item["x"])))
            y = int(round(float(item["y"])))
            w = int(round(float(item["width"])))
            h = int(round(float(item["height"])))
        except Exception as exc:
            raise ValueError("Seleção do Patch Balão Transparente inválida.") from exc
        if w <= 0 or h <= 0:
            raise ValueError("Seleção do Patch Balão Transparente possui área vazia.")
        x1, y1 = max(0, x), max(0, y)
        x2, y2 = min(width, x + w), min(height, y + h)
        if x2 <= x1 or y2 <= y1:
            raise ValueError("Seleção do Patch Balão Transparente está fora da imagem.")
        normalized.append({"index": index, "x": x1, "y": y1, "width": x2-x1, "height": y2-y1})
    return normalized

def _intersects(bbox, roi: dict) -> bool:
    x, y, w, h = bbox
    rx, ry, rw, rh = roi["x"], roi["y"], roi["width"], roi["height"]
    return x < rx + rw and x + w > rx and y < ry + rh and y + h > ry

def run_transparent_roi(source: Path, target: Path, selections, base_snapshot: Path | None = None) -> tuple[Path, dict]:
    started = time.monotonic()
    target.mkdir(parents=True, exist_ok=True)
    original = transparent._read_image(source)
    height, width = original.shape[:2]
    rois = _normalize_selections(selections, width, height)

    # Funções do patch protegido: Cleaner + Balloon Authorization + dilatação 3x3.
    base_mask, _components, balloon_authorization = transparent._detect_text_mask(source, target)
    before_pixels = int(np.count_nonzero(base_mask))

    binary = (base_mask > 0).astype(np.uint8)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    restricted_base = np.zeros_like(base_mask)
    selected_components, all_components = [], []

    for label in range(1, count):
        x, y, w, h, area = map(int, stats[label])
        hits = [roi["index"] for roi in rois if _intersects((x, y, w, h), roi)]
        row = {"label": label, "bbox": [x, y, w, h], "area": area, "roi_hits": hits}
        all_components.append(row)
        if hits:
            restricted_base[labels == label] = base_mask[labels == label]
            selected_components.append(row)

    if not selected_components:
        raise RuntimeError("Nenhum componente autorizado pelo Patch Balão Transparente intersecta as regiões selecionadas.")

    # Função protegida: autorização 9x9, agora só nos componentes escolhidos.
    authorized_mask = transparent._authorize_mask(restricted_base)
    authorized_pixels = int(np.count_nonzero(authorized_mask))
    if authorized_pixels == 0:
        raise RuntimeError("Máscara autorizada vazia após aplicar as regiões selecionadas.")

    base_path = target / "01_text_mask_roi.png"
    authorized_path = target / "02_authorized_mask_9x9_roi.png"
    overlay_path = target / "03_authorized_mask_overlay_roi.png"
    technical_path = target / "04_lama_text_only_roi.png"
    lama_meta_path = target / "lama_metadata_roi.json"

    if not cv2.imwrite(str(base_path), restricted_base):
        raise RuntimeError(f"Falha ao gravar {base_path}")
    if not cv2.imwrite(str(authorized_path), authorized_mask):
        raise RuntimeError(f"Falha ao gravar {authorized_path}")
    transparent._write_mask_overlay(original, authorized_mask, overlay_path)
    transparent._run_lama_worker(source, authorized_path, technical_path, lama_meta_path)

    technical = cv2.imread(str(technical_path))
    if technical is None or technical.shape != original.shape:
        raise RuntimeError("Resultado técnico do LaMa inválido.")
    changed = np.any(technical != original, axis=2)
    outside = changed & ~(authorized_mask > 0)
    outside_count = int(np.count_nonzero(outside))
    if outside_count:
        raise RuntimeError(f"Falha de segurança: {outside_count} pixel(s) alterado(s) fora da máscara ROI autorizada.")

    result = target / "04_lama_text_only.png"
    composition_mode = "technical_result_from_source"
    base_used = False
    if base_snapshot is not None:
        official = cv2.imread(str(base_snapshot))
        if official is None or official.shape != original.shape:
            raise RuntimeError("Snapshot da base oficial inválido ou incompatível.")
        composed = official.copy()
        composed[changed] = technical[changed]
        if not cv2.imwrite(str(result), composed):
            raise RuntimeError(f"Falha ao gravar {result}")
        composition_mode = "effective_changes_over_official_base"
        base_used = True
    else:
        if not cv2.imwrite(str(result), technical):
            raise RuntimeError(f"Falha ao gravar {result}")

    lama_meta = json.loads(lama_meta_path.read_text(encoding="utf-8"))
    meta = {
        "algorithm": ALGORITHM,
        "proof_phase": True,
        "promotion_allowed": False,
        "selection_count": len(rois),
        "selections": rois,
        "authorization_rule": "balloon_authorized_base_components_intersecting_roi",
        "base_mask_pixels_before_roi": before_pixels,
        "base_mask_pixels_after_roi": int(np.count_nonzero(restricted_base)),
        "authorized_mask_pixels_after_roi_9x9": authorized_pixels,
        "components_before_count": len(all_components),
        "components_selected_count": len(selected_components),
        "selected_components": selected_components,
        "balloon_authorization": balloon_authorization,
        "base_dilation": list(transparent.BASE_DILATION),
        "authorized_dilation": list(transparent.AUTHORIZED_DILATION),
        "lama_padding": transparent.LAMA_PADDING,
        "lama": lama_meta,
        "composition_mode": composition_mode,
        "effective_changed_pixels": int(np.count_nonzero(changed)),
        "technical_changed_outside_authorized_pixels": outside_count,
        "base_snapshot_used": base_used,
        "protected_patch_modified": False,
        "artifacts": {
            "restricted_text_mask": base_path.name,
            "authorized_mask": authorized_path.name,
            "overlay": overlay_path.name,
            "technical_result": technical_path.name,
            "result": result.name,
        },
        "elapsed_seconds": round(time.monotonic() - started, 3),
    }
    (target / "roi_report.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return result, meta
