"""Isolated worker for read-only Merged Nível III balloon analysis."""
import json
from pathlib import Path
import sys

from huggingface_hub import hf_hub_download
from ultralytics import YOLO

from .styled_balloon_detector import (
    ALGORITHM, CONFIDENCE, IOU, MODEL_FILE, MODEL_REPO, MODEL_REVISION, detect_page,
)


def run(request: Path) -> None:
    import cv2
    import numpy as np

    payload = json.loads(request.read_text(encoding="utf-8"))
    model_path = hf_hub_download(repo_id=MODEL_REPO, filename=MODEL_FILE,
                                 revision=MODEL_REVISION)
    model = YOLO(model_path)
    if getattr(model, "task", None) != "segment" or "balloon" not in {
        str(value).strip().lower() for value in (model.names or {}).values()
    }:
        raise RuntimeError("O segmentador carregado não reconhece a classe balloon.")
    pages = [detect_page(Path(path), model, cv2, np) for path in payload["images"]]
    candidates = [candidate for page in pages for candidate in page["styled_balloon_candidates"]]
    candidate_types = {}
    for candidate in candidates:
        kind = candidate["candidate_type"]
        candidate_types[kind] = candidate_types.get(kind, 0) + 1
    report = {
        "schema_version": 1, "algorithm": ALGORITHM,
        "input_stage": "MERGE",
        "status": "experimental_review_only", "images_analyzed": len(pages),
        "candidate_count": len(candidates), "candidate_types": candidate_types,
        "model": {"repo": MODEL_REPO, "file": MODEL_FILE,
                  "revision": MODEL_REVISION, "task": "segment", "class": "balloon",
                  "confidence": CONFIDENCE, "iou": IOU},
        "classifier": {
            "saturation_min": 70, "value_min": 70,
            "min_saturated_ratio": 0.35, "min_dominant_hue_ratio": 0.55,
            "min_interior_pixels": 120, "soft_gradient_gray_std_max": 13.0,
            "soft_gradient_chroma_ratio_min": 0.05,
            "tiled_shape_check": {
                "tile_height": 1800,
                "tile_overlap": 450,
                "prediction_confidence": CONFIDENCE,
                "candidate_type": "irregular_outline",
                "max_circularity": 0.5,
                "max_solidity": 0.9,
                "purpose": "Reexaminar balões em recortes maiores e marcar contornos irregulares; requer revisão visual.",
            },
            "reference_examples": {
                "estilizado_antes.png": {"saturated_ratio": 0.76686,
                                         "dominant_hue_ratio": 0.9853,
                                         "candidate_type": "saturated_styled"},
                "degrade_antes.png": {"saturated_ratio": 0.0014,
                                      "gray_std_bright_pixels": 8.62,
                                      "chroma_ratio_bright_pixels": 0.86938,
                                      "candidate_type": "soft_gradient"},
                "gradiente_suave_antes.png": {"saturated_ratio": 0.0119,
                                               "gray_std_bright_pixels": 10.0714,
                                               "chroma_ratio_bright_pixels": 0.98396,
                                               "candidate_type": "soft_gradient"},
            },
            "note": "Heurística inicial calibrada pelos três previews; candidatos requerem revisão visual.",
        },
        "pages": pages,
    }
    destination = Path(payload["report"])
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")


if __name__ == "__main__":
    run(Path(sys.argv[1]))
