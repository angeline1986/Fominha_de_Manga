"""Validate and process one TextOff Merged Level II chapter."""
from __future__ import annotations

import json
from pathlib import Path
import time

import cv2
import numpy as np
from PIL import Image
from .artifact_paths import artifact_file, artifact_ref, prepare_artifact_dirs
from .level2_vision import (
    MAX_MPS_PAGES_PER_MODEL,
    SUPPORTED, _atomic_json, _authorized_deferred_mask, _inpaint, _lama_model,
    _release_inference_cache,
)
from .level2_manual_protection import progress_detail, protect_level2_masks
from .level2_provenance import assert_unchanged, page_provenance
from central_v2.backend.orchestration.textoff_special.artifacts import sha256
from .level2_report import build_report
from .level2_page_output import compose_output, load_page_inputs, verify_reset_input
from .level2_reset_base import RESET_BASE_CONTRACT


def process(source_dir: Path, level1_dir: Path, output_dir: Path,
            report_path: Path, progress_path: Path | None = None,
            runtime: dict | None = None, candidate_pages: set[str] | None = None,
            protected_occurrences: dict[str, list[dict]] | None = None,
            protection_source: dict | None = None,
            reset_bases: dict | None = None) -> dict:
    started = time.perf_counter()
    source_dir, level1_dir, output_dir = source_dir.resolve(), level1_dir.resolve(), output_dir.resolve()
    report_file = artifact_file(level1_dir, "json/level1-balloon-report.json", "json")
    manifest_file = artifact_file(level1_dir, "json/clean-manifest.json", "json")
    if report_file is None or manifest_file is None:
        raise FileNotFoundError("level1-balloon-report.json ou clean-manifest.json do Nível I ausente.")
    level1_report_hash = sha256(report_file)
    level1_manifest_hash = sha256(manifest_file)
    report = json.loads(report_file.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    if sha256(report_file) != level1_report_hash or sha256(manifest_file) != level1_manifest_hash:
        raise ValueError("Autoridade do Nível I mudou durante sua leitura.")
    if manifest.get("integrity_ok") is not True or manifest.get("level1", {}).get("algorithm") != "textoff_level1_balloon_transparency_gate_v4":
        raise ValueError("Reexecute o Nível I para vincular cada balão transparente à sua máscara.")
    pages = {item.get("source"): item for item in report.get("pages", []) if isinstance(item, dict)}
    sources = sorted(path for path in source_dir.iterdir() if path.is_file() and path.suffix.lower() in SUPPORTED)
    if not sources:
        raise ValueError("Nível II: nenhuma imagem MERGE encontrada.")
    if candidate_pages is None:
        candidate_pages = {name for name, page in pages.items()
                           if page.get("transparent_balloons") or page.get("transparent_components_deferred")}
    if not candidate_pages or not candidate_pages.issubset({path.name for path in sources}):
        raise ValueError("Nível II requer páginas candidatas válidas do manifesto Nível I.")
    cleaner_names = manifest.get("clean_artifacts") or []
    expected_names = {path.stem + "_clean" + path.suffix for path in sources}
    if (len(cleaner_names) != len(sources)
            or {Path(str(name)).name for name in cleaner_names} != expected_names
            or any(artifact_file(level1_dir, name, "clean") is None for name in cleaner_names)):
        raise ValueError("As imagens do Nível I não correspondem ao MERGE oficial atual.")
    if runtime is None:
        runtime = {}
    model = runtime.get("model")
    model_path = runtime.get("model_path")
    device = runtime.get("device")
    prepare_artifact_dirs(output_dir)
    page_results = []
    protection_totals = {key: 0 for key in ("protected_occurrences", "protected_pixels",
        "mask_pixels_before_protection", "mask_pixels_after_protection")}
    protected_types = set()
    analyzed_total = 0
    provenance_records = []
    protected_occurrences = protected_occurrences or {}
    protection_source = protection_source or {"kind": "UNKNOWN", "path": None,
                                              "sha256": None, "revision": None}
    for index, source in enumerate(sources, 1):
        page = pages.get(source.name)
        if page is None:
            raise ValueError(f"Nível I não registrou {source.name}.")
        if source.name not in candidate_pages:
            continue
        analyzed_total += 1
        clean_name = source.stem + "_clean" + source.suffix
        clean_reference = artifact_ref("clean", clean_name)
        clean_path = artifact_file(level1_dir, clean_reference, "clean")
        label_path = artifact_file(level1_dir, page.get("transparent_mask_artifact"), "mask")
        if clean_path is None or label_path is None:
            raise FileNotFoundError(f"Artefatos de Nível I ausentes para {source.name}.")
        (original, level1, output_base, reset_source, reset_input,
         consumed_sources) = load_page_inputs(source, clean_path, reset_bases)
        deferred_name = page.get("deferred_text_mask_artifact")
        deferred_path = artifact_file(level1_dir, deferred_name, "mask") if deferred_name else None
        if deferred_name and deferred_path is None:
            raise ValueError(f"Máscara de texto adiado ausente ou inválida para {source.name}.")
        lineage = {"level1_report_sha256": level1_report_hash,
                   "level1_mask_sha256": sha256(label_path),
                   "deferred_mask_sha256": sha256(deferred_path) if deferred_path else None}
        lineage_paths = {"level1_report": (report_file, level1_report_hash),
                         "level1_mask": (label_path, lineage["level1_mask_sha256"])}
        if deferred_path:
            lineage_paths["deferred_mask"] = (deferred_path, lineage["deferred_mask_sha256"])
        labels = cv2.imread(str(label_path), cv2.IMREAD_UNCHANGED)
        if labels is None or labels.ndim != 2 or labels.shape != original.shape[:2] or level1.shape != original.shape:
            raise ValueError(f"Dimensões inválidas nos artefatos de {source.name}.")
        deferred = np.zeros(labels.shape, dtype=np.uint8)
        if deferred_path:
            deferred = cv2.imread(str(deferred_path), cv2.IMREAD_GRAYSCALE)
            if deferred is None or deferred.shape != labels.shape:
                raise ValueError(f"Máscara de texto adiado ausente ou inválida para {source.name}.")
        elif int(page.get("transparent_components_deferred") or 0):
            raise ValueError(f"Reexecute o Nível I para gerar as máscaras de texto adiado de {source.name}.")
        if (sha256(report_file) != level1_report_hash
                or sha256(label_path) != lineage["level1_mask_sha256"]):
            raise ValueError(f"Proveniência do Nível I mudou durante a leitura de {source.name}.")
        if deferred_path and sha256(deferred_path) != lineage["deferred_mask_sha256"]:
            raise ValueError(f"Máscara adiada mudou durante a leitura de {source.name}.")
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
        mask_before_protection = int(np.count_nonzero(mask))
        protected = protected_occurrences.get(source.name, [])
        balloon_masks, protection = protect_level2_masks(balloon_masks, protected, labels.shape)
        mask = np.zeros(labels.shape, dtype=np.uint8)
        for balloon_row, balloon_mask in zip(balloons, balloon_masks):
            balloon_row["mask_pixels"] = int(np.count_nonzero(balloon_mask))
            mask = cv2.bitwise_or(mask, balloon_mask)
        if deferred_components and mask_before_protection == 0:
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
        result, outside, changed = compose_output(level1, output_base, final, mask)
        if outside:
            raise RuntimeError(f"Integridade do Nível II violada fora da máscara em {source.name}.")
        clean_reference = artifact_ref("clean", clean_name)
        mask_reference = artifact_ref("mask", f"{source.stem}_text_mask.png")
        if changed:
            Image.fromarray(result).save(output_dir / clean_reference)
        Image.fromarray(mask, mode="L").save(output_dir / mask_reference)
        mask_pixels = int(np.count_nonzero(mask))
        for key in protection_totals:
            protection_totals[key] += protection[key]
        protected_types.update(protection["protected_types"])
        provenance, consumed = page_provenance(
            source, clean_path, output_dir / clean_reference if changed else clean_path,
            output_dir / mask_reference, protection_source, protected, consumed_sources,
            lineage, lineage_paths)
        if reset_input:
            provenance["reset_base_source"] = reset_source
            consumed["reset_base"] = reset_input
            verify_reset_input(reset_input)
        provenance_records.append(consumed)
        page_results.append({"source": source.name, "clean": clean_reference if changed else None,
                             "level1_clean": clean_reference,
                             "mask": mask_reference, "transparent_balloons": balloons,
                             "mask_pixels": mask_pixels, "changed_pixels": changed, **provenance,
                             "changed_outside_mask": outside, **protection})
        if progress_path:
            _atomic_json(progress_path, {"percent": round(index * 95 / len(sources)),
                "detail": progress_detail(analyzed_total, len(candidate_pages), source.name, protection)})
    result = build_report(started, model, model_path, device, analyzed_total,
                          len(sources), page_results, protection_totals,
                          protected_types, level1_manifest_hash)
    if reset_bases is not None:
        result["reset_base_contract"] = RESET_BASE_CONTRACT
    assert_unchanged(provenance_records)
    if sha256(report_file) != level1_report_hash or sha256(manifest_file) != level1_manifest_hash:
        raise ValueError("Autoridade do Nível I mudou durante a execução.")
    _atomic_json(report_path, result)
    if progress_path:
        _atomic_json(progress_path, {"percent": 100, "detail": "Nível II validado"})
    return result
