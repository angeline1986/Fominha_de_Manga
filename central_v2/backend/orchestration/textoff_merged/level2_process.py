"""Validate and process one TextOff Merged Level II chapter."""
from __future__ import annotations

import json
from pathlib import Path
import time

import cv2
import numpy as np
from PIL import Image

from .level2_vision import (
    ALGORITHM, AUTHORIZED_DILATION, BASE_DILATION, LAMA_PADDING,
    MAX_MPS_PAGES_PER_MODEL, REFERENCE_RECIPE,
    SUPPORTED, _atomic_json, _authorized_deferred_mask, _inpaint, _lama_model,
    _release_inference_cache,
)

def process(source_dir: Path, level1_dir: Path, output_dir: Path,
            report_path: Path, progress_path: Path | None = None,
            runtime: dict | None = None) -> dict:
    started = time.perf_counter()
    source_dir, level1_dir, output_dir = source_dir.resolve(), level1_dir.resolve(), output_dir.resolve()
    report_file = level1_dir / "level1-balloon-report.json"
    manifest_file = level1_dir / "clean-manifest.json"
    report = json.loads(report_file.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    if manifest.get("integrity_ok") is not True or manifest.get("level1", {}).get("algorithm") != "textoff_level1_balloon_transparency_gate_v4":
        raise ValueError("Reexecute o Nível I para vincular cada balão transparente à sua máscara.")

    pages = {item.get("source"): item for item in report.get("pages", []) if isinstance(item, dict)}
    sources = sorted(path for path in source_dir.iterdir() if path.is_file() and path.suffix.lower() in SUPPORTED)
    if not sources:
        raise ValueError("Nível II: nenhuma imagem MERGE encontrada.")
    cleaner_names = manifest.get("clean_artifacts") or []
    if set(cleaner_names) != {path.name.replace(path.suffix, "_clean" + path.suffix) for path in sources}:
        raise ValueError("As imagens do Nível I não correspondem ao MERGE oficial atual.")

    if runtime is None:
        runtime = {}

    model = runtime.get("model")
    model_path = runtime.get("model_path")
    device = runtime.get("device")
    output_dir.mkdir(parents=True, exist_ok=True)
    page_results = []
    changed_total = mask_total = 0
    for index, source in enumerate(sources, 1):
        page = pages.get(source.name)
        if page is None:
            raise ValueError(f"Nível I não registrou {source.name}.")
        clean_name = source.stem + "_clean" + source.suffix
        clean_path = level1_dir / clean_name
        label_name = page.get("transparent_mask_artifact")
        label_path = level1_dir / str(label_name or "")
        if not clean_path.is_file() or not label_path.is_file():
            raise FileNotFoundError(f"Artefatos de Nível I ausentes para {source.name}.")
        with Image.open(source) as image:
            original = np.asarray(image.convert("RGB"))
        with Image.open(clean_path) as image:
            level1 = np.asarray(image.convert("RGB"))
        labels = cv2.imread(str(label_path), cv2.IMREAD_UNCHANGED)
        if labels is None or labels.ndim != 2 or labels.shape != original.shape[:2] or level1.shape != original.shape:
            raise ValueError(f"Dimensões inválidas nos artefatos de {source.name}.")
        deferred_name = page.get("deferred_text_mask_artifact")
        deferred = np.zeros(labels.shape, dtype=np.uint8)
        if deferred_name:
            if not isinstance(deferred_name, str) or Path(deferred_name).name != deferred_name:
                raise ValueError(f"Nome de máscara adiada inválido para {source.name}.")
            deferred_path = level1_dir / deferred_name
            deferred = cv2.imread(str(deferred_path), cv2.IMREAD_GRAYSCALE)
            if deferred is None or deferred.shape != labels.shape:
                raise ValueError(f"Máscara de texto adiado ausente ou inválida para {source.name}.")
        elif int(page.get("transparent_components_deferred") or 0):
            raise ValueError(f"Reexecute o Nível I para gerar as máscaras de texto adiado de {source.name}.")
        balloons, balloon_masks = [], []
        mask = np.zeros(labels.shape, dtype=np.uint8)
        deferred_components = int(page.get("transparent_components_deferred") or 0)
        for balloon in page.get("transparent_balloons", []):
            label = int(balloon.get("mask_label") or 0)
            if label <= 0:
                raise ValueError(f"Nível I sem mask_label para balão em {source.name}; reexecute o Nível I.")
            balloon_area = labels == label
            if not np.any(balloon_area):
                raise ValueError(f"Rótulo {label} sem pixels para balão em {source.name}; reexecute o Nível I.")
            balloon_mask = _authorized_deferred_mask(deferred, balloon_area)
            mask = cv2.bitwise_or(mask, balloon_mask)
            balloon_masks.append(balloon_mask)
            balloons.append({"balloon": balloon.get("balloon"), "mask_label": label,
                             "mask_pixels": int(np.count_nonzero(balloon_mask)),
                             "deferred_cleaner_pixels": int(np.count_nonzero(
                                 (deferred > 0) & balloon_area))})
        if deferred_components and not np.any(mask):
            raise RuntimeError(f"Nível II não formou máscara para resíduos adiados em {source.name}.")
        final = original.copy()
        for balloon_mask in balloon_masks:
            if not np.any(balloon_mask):
                continue
            model_inferences = runtime.get("model_inferences", 0)
            if (model is not None and device == "mps"
                    and model_inferences >= MAX_MPS_PAGES_PER_MODEL):
                model = None
                runtime.update(model=None, model_path=None, device=None, model_inferences=0)
                _release_inference_cache(device)
                device = None
            if model is None:
                model, model_path, device = _lama_model()
                runtime.update(model=model, model_path=model_path, device=device,
                               model_inferences=0)
            final = _inpaint(final, balloon_mask, model)
            runtime["model_inferences"] = runtime.get("model_inferences", 0) + 1
            _release_inference_cache(device)
        result = level1.copy()
        active = mask > 0
        result[active] = final[active]
        outside = int(np.count_nonzero(np.any(result != level1, axis=2) & ~active))
        if outside:
            raise RuntimeError(f"Integridade do Nível II violada fora da máscara em {source.name}.")
        Image.fromarray(result).save(output_dir / clean_name)
        Image.fromarray(mask, mode="L").save(output_dir / f"{source.stem}_text_mask.png")
        changed = int(np.count_nonzero(np.any(result != level1, axis=2)))
        mask_pixels = int(np.count_nonzero(mask))
        changed_total += changed
        mask_total += mask_pixels
        page_results.append({"source": source.name, "clean": clean_name,
                             "mask": f"{source.stem}_text_mask.png", "transparent_balloons": balloons,
                             "mask_pixels": mask_pixels, "changed_pixels": changed,
                             "changed_outside_mask": outside})
        if progress_path:
            _atomic_json(progress_path, {"percent": round(index * 95 / len(sources)),
                                         "detail": f"Reconstruindo texto autorizado ({index}/{len(sources)})"})

    result = {
        "schema_version": 1,
        "algorithm": ALGORITHM,
        "mask_sources": ["Level I deferred Cleaner V2 components inside the matching transparent balloon"],
        "base_dilation": [BASE_DILATION, BASE_DILATION],
        "authorized_dilation": [AUTHORIZED_DILATION, AUTHORIZED_DILATION],
        "lama_padding": LAMA_PADDING,
        "reference_recipe": REFERENCE_RECIPE,
        "source_stage": "MERGED_NIVEL_I",
        "text_detector": "Cleaner V2 deferred text mask",
        "text_recognition": False,
        "inpainter": "anime-manga-big-lama" if model else None,
        "model_path": model_path,
        "device": device,
        "pages_analyzed": len(sources),
        "duration_seconds": round(time.perf_counter() - started, 3),
        "pages_with_text": sum(page["mask_pixels"] > 0 for page in page_results),
        "mask_pixels": mask_total,
        "changed_pixels": changed_total,
        "outcome": "visual_changes" if changed_total else "no_visual_change",
        "integrity_ok": all(page["changed_outside_mask"] == 0 for page in page_results),
        "pages": page_results,
    }
    _atomic_json(report_path, result)
    if progress_path:
        _atomic_json(progress_path, {"percent": 100, "detail": "Nível II validado"})
    return result
