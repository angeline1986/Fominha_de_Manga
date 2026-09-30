"""Bind existing image-domain functions only inside a dedicated worker process."""
import importlib
import json
from pathlib import Path
import sys
import time

from .catalog import runtime_folder, treatment_for
from .artifacts import write_json


def run_treatment(key: str, source: Path, target: Path, selections: list) -> tuple:
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
        result, metadata = getattr(adapter, treatment.function)(source, target, selections)
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
    mask_path, result_path = target / "01_authorized_mask.png", target / "02_lama_result.png"
    metadata_path = target / "lama_metadata.json"
    if not cv2.imwrite(str(mask_path), mask):
        raise RuntimeError("Não foi possível preparar a máscara do tratamento.")
    started = time.monotonic()
    patch._run_lama_worker(source, mask_path, result_path, metadata_path)
    metadata = {"algorithm": f"textoff_merged_level{level}_from_level1_mask_v1",
                "proof_phase": True, "promotion_allowed": False,
                "runtime_treatment": key, "authorization_rule": "level1_deferred_text",
                "artifacts": {"authorized_mask": mask_path.name, "result": result_path.name},
                "lama": json.loads(metadata_path.read_text(encoding="utf-8"))}
    return result_path, metadata, {"lama_seconds": round(time.monotonic() - started, 3)}
