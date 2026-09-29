"""Create Level II masks from the public Level I authorization report."""
from pathlib import Path

from processamento.limpeza_baloes.cleaner_v2 import balloon_authorization as policy

LEVEL1_ARTIFACT_ALGORITHM = "textoff_level1_balloon_transparency_gate_v4"


def save_deferred_artifacts(images, raw_masks, output_dir: Path, report: dict) -> None:
    try:
        import cv2
        import numpy as np
        from huggingface_hub import hf_hub_download
        from ultralytics import YOLO
    except ImportError as exc:
        raise RuntimeError("TextOff Merged requer cv2, numpy, huggingface_hub e ultralytics.") from exc

    try:
        model = YOLO(hf_hub_download(
            repo_id=policy.MODEL_REPO,
            filename=policy.MODEL_FILE,
            revision=policy.MODEL_REVISION,
        ))
    except Exception as exc:
        raise RuntimeError("V2 não conseguiu carregar o segmentador de balões.") from exc
    if getattr(model, "task", None) != "segment" or "balloon" not in {
        str(value).strip().lower() for value in (model.names or {}).values()
    }:
        raise RuntimeError("O modelo de Nível I não é um segmentador de balões válido.")

    pages = {page["source"]: page for page in report.get("pages", [])}
    for image, raw_mask_path in zip(images, raw_masks, strict=True):
        page = pages.get(image.name)
        if page is None:
            raise RuntimeError(f"Relatório do Nível I não contém {image.name}.")
        original = cv2.imread(str(image))
        raw_mask = cv2.imread(str(raw_mask_path), cv2.IMREAD_GRAYSCALE)
        if original is None or raw_mask is None or original.shape[:2] != raw_mask.shape[:2]:
            raise RuntimeError(f"Não foi possível validar as máscaras de {image.name}.")
        try:
            prediction = model.predict(source=original, conf=policy.CONF, iou=policy.IOU, verbose=False)[0]
        except Exception as exc:
            raise RuntimeError(f"V2 falhou ao produzir a máscara de balões de {image.name}.") from exc

        labels, transparent_mask, mask_labels = _transparent_balloon_masks(original, prediction, cv2, np)
        reported_count = len(page.get("transparent_balloons", []))
        if len(mask_labels) != reported_count:
            raise RuntimeError(f"Detecção transparente divergente em {image.name}; Nível I cancelado.")
        _bind_mask_labels(page.get("transparent_balloons", []), mask_labels, image.name)
        deferred = _deferred_text_mask(raw_mask, page, transparent_mask, cv2, np)
        transparent_name = f"{image.stem}_transparent_balloons.png"
        if not cv2.imwrite(str(output_dir / transparent_name), labels):
            raise RuntimeError(f"V2 não conseguiu salvar máscaras transparentes de {image.name}.")
        deferred_name = None
        if np.any(deferred):
            deferred_name = f"{image.stem}_deferred_text.png"
            if not cv2.imwrite(str(output_dir / deferred_name), deferred):
                raise RuntimeError(f"V2 não conseguiu salvar texto adiado de {image.name}.")
        if int(page.get("transparent_components_deferred") or 0) and not deferred_name:
            raise RuntimeError(f"V2 não validou texto adiado de {image.name}; Nível I cancelado.")
        page.update({
            "transparent_mask_artifact": transparent_name,
            "deferred_text_mask_artifact": deferred_name,
            "deferred_text_mask_pixels": int(np.count_nonzero(deferred)),
        })
    report["algorithm"] = LEVEL1_ARTIFACT_ALGORITHM


def _bind_mask_labels(balloons: list[dict], mask_labels: dict[int, dict], source_name: str) -> None:
    for balloon in balloons:
        detection_index = int(balloon.get("balloon") or 0)
        mapping = mask_labels.get(detection_index)
        if mapping is None:
            raise RuntimeError(f"Rótulo da máscara transparente ausente em {source_name}; Nível I cancelado.")
        if list(balloon.get("bbox") or []) != mapping["bbox"]:
            raise RuntimeError(f"Geometria do balão divergiu em {source_name}; Nível I cancelado.")
        balloon["mask_label"] = mapping["mask_label"]


def _transparent_balloon_masks(original, prediction, cv2, np):
    shape = original.shape[:2]
    labels = np.zeros(shape, dtype=np.uint16)
    combined = np.zeros(shape, dtype=bool)
    transparent_count = 0
    mask_labels = {}
    if prediction.masks is None:
        return labels, combined, mask_labels
    for detection_index, polygon in enumerate(prediction.masks.xy, 1):
        points = np.asarray(polygon, dtype=np.int32)
        if len(points) < 3:
            continue
        mask = np.zeros(shape, dtype=np.uint8)
        cv2.fillPoly(mask, [points], 255)
        x, y, width, height = cv2.boundingRect(points)
        margin = max(policy.BALLOON_INTERIOR_ERODE_MIN, min(
            policy.BALLOON_INTERIOR_ERODE_MAX,
            int(round(min(width, height) * policy.BALLOON_INTERIOR_ERODE_RATIO)),
        ))
        if margin > 0:
            size = 2 * margin + 1
            interior = cv2.erode(mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (size, size)))
            if np.count_nonzero(interior):
                mask = interior
        if not policy.measure_transparency(original, mask)["transparent"]:
            continue
        transparent_count += 1
        labels[mask > 0] = transparent_count
        mask_labels[detection_index] = {
            "mask_label": transparent_count, "bbox": [int(x), int(y), int(width), int(height)],
        }
        combined |= mask > 0
    return labels, combined, mask_labels


def _deferred_text_mask(raw_mask, page, transparent_mask, cv2, np):
    binary = (raw_mask > 0).astype(np.uint8)
    _, components = cv2.connectedComponents(binary, 8)
    deferred = np.zeros_like(raw_mask)
    for decision in page.get("component_decisions", []):
        if decision.get("reason") != "transparent_balloon_deferred":
            continue
        component_id = int(decision.get("component") or 0)
        if component_id <= 0:
            continue
        safe_pixels = (components == component_id) & transparent_mask
        deferred[safe_pixels] = raw_mask[safe_pixels]
    return deferred
