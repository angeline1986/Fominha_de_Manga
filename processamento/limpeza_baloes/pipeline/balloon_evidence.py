"""Milestone 1B — structural balloon evidence, without eligibility decisions.

Uses exactly the model/revision/conf/iou contract currently used by the legacy
balloon authorization stage, but never reads or mutates Cleaner V2 _clean/_mask
artifacts. It only measures candidate boxes against detected balloon masks.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

MODEL_REPO = "huyvux3005/manga109-segmentation-bubble"
MODEL_FILE = "best.pt"
MODEL_REVISION = "f9a4108c4955136a810e5e92207972f3fb3a65fd"
CONF = 0.25
IOU = 0.45
ALGORITHM = "textoff_pipeline_balloon_evidence_v1"


def model_contract() -> dict[str, Any]:
    return {
        "repo": MODEL_REPO,
        "file": MODEL_FILE,
        "revision": MODEL_REVISION,
        "task": "segment",
        "class": "balloon",
        "conf": CONF,
        "iou": IOU,
    }


def _load_dependencies():
    try:
        import cv2
        import numpy as np
        from huggingface_hub import hf_hub_download
        from ultralytics import YOLO
    except ImportError as exc:
        raise RuntimeError(
            "Balloon Evidence requer cv2, numpy, huggingface_hub e ultralytics."
        ) from exc
    return cv2, np, hf_hub_download, YOLO


def _load_model(hf_hub_download, YOLO):
    try:
        model_path = hf_hub_download(
            repo_id=MODEL_REPO,
            filename=MODEL_FILE,
            revision=MODEL_REVISION,
        )
        model = YOLO(model_path)
    except Exception as exc:
        raise RuntimeError(
            "Balloon Evidence não conseguiu carregar o segmentador de balões."
        ) from exc

    names = {str(v).strip().lower() for v in (model.names or {}).values()}
    if getattr(model, "task", None) != "segment" or "balloon" not in names:
        raise RuntimeError(
            "Modelo inválido para Balloon Evidence: "
            f"task={getattr(model, 'task', None)!r}, classes={model.names!r}"
        )
    return model


def _resolve_source_path(raw_json: Path, original_path: Any, image_path: Any) -> Path:
    candidates = []
    for value in (original_path, image_path):
        if not value:
            continue
        p = Path(str(value)).expanduser()
        candidates.append(p if p.is_absolute() else (raw_json.parent / p))
    for path in candidates:
        resolved = path.resolve()
        if resolved.is_file():
            return resolved
    rendered = ", ".join(str(p) for p in candidates) or "<nenhum caminho no raw JSON>"
    raise FileNotFoundError(
        "Balloon Evidence não encontrou a imagem usada pelo CTD. "
        f"Candidatos de caminho: {rendered}"
    )


def analyze_page(
    raw_json: Path,
    original_path: Any,
    image_path: Any,
    candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    cv2, np, hf_hub_download, YOLO = _load_dependencies()
    source = _resolve_source_path(Path(raw_json).resolve(), original_path, image_path)
    original = cv2.imread(str(source))
    if original is None:
        raise RuntimeError(f"Balloon Evidence falhou ao ler a imagem: {source}")

    model = _load_model(hf_hub_download, YOLO)
    try:
        result = model.predict(source=original, conf=CONF, iou=IOU, verbose=False)[0]
    except Exception as exc:
        raise RuntimeError(
            f"Balloon Evidence falhou ao segmentar {source.name}."
        ) from exc

    height, width = original.shape[:2]
    balloon_masks: list[Any] = []
    if result.masks is not None:
        for poly in result.masks.xy:
            pts = np.asarray(poly, dtype=np.int32)
            if len(pts) < 3:
                continue
            mask = np.zeros((height, width), dtype=np.uint8)
            cv2.fillPoly(mask, [pts], 255)
            if np.count_nonzero(mask):
                balloon_masks.append(mask)

    evidence_by_id: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        x1, y1, x2, y2 = map(int, candidate["bbox"])
        x1c, y1c = max(0, x1), max(0, y1)
        x2c, y2c = min(width, x2), min(height, y2)
        if x2c <= x1c or y2c <= y1c:
            raise ValueError(
                f"Candidate {candidate['candidate_id']} is outside image bounds."
            )

        box_area = (x2c - x1c) * (y2c - y1c)
        cx = min(width - 1, max(0, int((x1 + x2) / 2)))
        cy = min(height - 1, max(0, int((y1 + y2) / 2)))

        union = np.zeros((height, width), dtype=np.uint8)
        for mask in balloon_masks:
            union = cv2.bitwise_or(union, mask)
        union_inside = int(np.count_nonzero(union[y1c:y2c, x1c:x2c]))
        box_inside_percent = (union_inside / box_area * 100.0) if box_area else 0.0

        best_id = None
        best_overlap = 0
        best_balloon_area = 0
        for idx, mask in enumerate(balloon_masks, start=1):
            overlap = int(np.count_nonzero(mask[y1c:y2c, x1c:x2c]))
            if overlap > best_overlap:
                best_overlap = overlap
                best_balloon_area = int(np.count_nonzero(mask))
                best_id = idx

        evidence_by_id[candidate["candidate_id"]] = {
            "algorithm": ALGORITHM,
            "balloons_detected": len(balloon_masks),
            "best_balloon_id": best_id,
            "box_inside_balloon_percent": round(box_inside_percent, 4),
            "center_inside_balloon": bool(union[cy, cx] > 0),
            "best_balloon_box_overlap_percent": round(
                best_overlap / box_area * 100.0, 4
            ) if box_area else 0.0,
            "balloon_inside_box_percent": round(
                best_overlap / best_balloon_area * 100.0, 4
            ) if best_balloon_area else 0.0,
        }

    from .region_evidence import measure_regions

    return {
        "source_image": str(source),
        "image_width": width,
        "image_height": height,
        "balloons_detected": len(balloon_masks),
        "model": model_contract(),
        "candidates": evidence_by_id,
        # Reuse these exact masks. Individual/union semantics in v1 stay intact.
        "region_evidence": measure_regions(original, balloon_masks, candidates),
    }
