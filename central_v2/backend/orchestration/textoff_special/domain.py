"""Bind existing image-domain functions only inside a dedicated worker process."""
import importlib
import json
from pathlib import Path
import sys
import time

import cv2
import numpy as np

from .catalog import runtime_folder, treatment_for
from .artifacts import write_json


def run_treatment(key: str, source: Path, target: Path, selections: list,
                  *, approved_check_rois: bool = False) -> tuple:
    expected_prefix = (runtime_folder(key) / ".venv").resolve()
    if Path(sys.prefix).resolve() != expected_prefix:
        raise RuntimeError("O domínio deve executar exclusivamente na venv do tratamento.")
    treatment = treatment_for(key)
    base = importlib.import_module("processamento.limpeza_baloes.patch_degrade_experimento")
    transparent = importlib.import_module("processamento.limpeza_baloes.patch_balao_transparente_experimento")
    adapter = importlib.import_module(f"processamento.limpeza_baloes.{treatment.module}")
    timings = {}

    def measured(name, operation):
        def invoke(*args, **kwargs):
            started = time.monotonic()
            try:
                return operation(*args, **kwargs)
            finally:
                timings[name] = round(time.monotonic() - started, 3)
        return invoke

    old_python, old_cleaner = base.CLEANER_PY, base._run_cleaner
    old_lama = transparent._run_lama_worker
    try:
        # Both nested executors read this binding. No V1 runtime is launched.
        base.CLEANER_PY = Path(sys.executable)
        base._run_cleaner = measured("cleaner_seconds", old_cleaner)
        transparent._run_lama_worker = measured("lama_seconds", old_lama)
        function = getattr(adapter, treatment.function)
        if key == "gradiente_suave":
            result = target / "gradiente_suave.png"
            boxes = [tuple(selection[name] for name in ("x", "y", "width", "height"))
                     for selection in selections]
            metadata = function(source, result, boxes,
                                target / "gradiente_suave_report.json")
            _write_smooth_authorization(target, metadata)
        else:
            if approved_check_rois and key != "degrade":
                raise ValueError("Aprovação do Check só se aplica ao Degradê.")
            if approved_check_rois:
                result, metadata = function(source, target, selections, approved_check_rois=True)
            else:
                result, metadata = function(source, target, selections)
            metadata.setdefault("artifacts", {})["authorized_mask"] = "roi_authorized_mask.png"
            if key == "degrade":
                report = json.loads((target / "balloon_authorization.json").read_text(encoding="utf-8"))
                metadata["balloon_authorization"] = report.get("model")
        return result, metadata, timings
    finally:
        base.CLEANER_PY, base._run_cleaner = old_python, old_cleaner
        transparent._run_lama_worker = old_lama
        write_json(target.parent / "worker-timings.json", timings)

def run_pre_authorized_treatment(key: str, level: str, source: Path, target: Path,
                                 authorization_mask: Path) -> tuple:
    """Apply a Level I-derived mask using the selected treatment's own runtime."""
    import cv2
    import numpy as np

    expected_prefix = (runtime_folder(key) / ".venv").resolve()
    if Path(sys.prefix).resolve() != expected_prefix:
        raise RuntimeError("O tratamento não está na venv declarada para o nível.")
    target.mkdir(parents=True, exist_ok=True)
    image = cv2.imread(str(source))
    mask = cv2.imread(str(authorization_mask), cv2.IMREAD_GRAYSCALE)
    if image is None or mask is None or image.shape[:2] != mask.shape:
        raise ValueError("Imagem e máscara autorizada incompatíveis.")
    if not np.any(mask):
        raise ValueError("A máscara autorizada está vazia.")
    patch = importlib.import_module(
        "processamento.limpeza_baloes.patch_balao_transparente_experimento")
    base = importlib.import_module("processamento.limpeza_baloes.patch_degrade_experimento")
    mask_path, result_path = target / "01_authorized_mask.png", target / "02_lama_result.png"
    metadata_path = target / "lama_metadata.json"
    if not cv2.imwrite(str(mask_path), mask):
        raise RuntimeError("Não foi possível preparar a máscara do tratamento.")
    old_python = base.CLEANER_PY
    base.CLEANER_PY = Path(sys.executable)
    started = time.monotonic()
    try:
        patch._run_lama_worker(source, mask_path, result_path, metadata_path)
    finally:
        base.CLEANER_PY = old_python
    metadata = {"algorithm": f"textoff_merged_level{level}_from_level1_mask_v1",
                "proof_phase": True, "promotion_allowed": False,
                "runtime_treatment": key, "authorization_rule": "level1_deferred_text",
                "artifacts": {"authorized_mask": mask_path.name, "result": result_path.name},
                "lama": json.loads(metadata_path.read_text(encoding="utf-8"))}
    return result_path, metadata, {"lama_seconds": round(time.monotonic() - started, 3)}


def _write_smooth_authorization(target: Path, metadata: dict) -> None:
    shape = cv2.imread(str(target / "gradiente_suave.png"))
    if shape is None:
        raise RuntimeError("Resultado do Gradiente Suave ausente.")
    mask = np.zeros(shape.shape[:2], dtype=np.uint8)
    for region in metadata["regions"]:
        x1, y1, x2, y2 = region["write_bbox_pixels"]
        mask[y1:y2, x1:x2] = 255
    path = target / "authorized_mask.png"
    if not cv2.imwrite(str(path), mask):
        raise RuntimeError("Não foi possível salvar a máscara de validação.")
    metadata["artifacts"] = {"authorized_mask": path.name}
