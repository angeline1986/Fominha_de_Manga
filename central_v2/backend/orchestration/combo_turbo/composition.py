"""Pixel-exact, isolated composition of validated Sólidos and Glass results."""
import json
import os
import shutil
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

from central_v2.backend.orchestration.textoff_special.artifacts import sha256

from .composition_inputs import prepare_inputs
from .models import result
from .validation import validate_page


def compose_page(manga, provider, chapter, page, *, level1_path, output_dir,
                 solids_path=None, glass_path=None, mask_path=None):
    """Compose one page into a new disposable bundle; never writes input stages."""
    from .models import valid_chapter_id, valid_page_id
    if not valid_chapter_id(chapter) or not valid_page_id(page):
        return result("COMBO_TURBO", chapter, page, "INVALID", reasons=["INVALID_PAGE_IDENTITY"])
    if solids_path is None and glass_path is None:
        return result("COMBO_TURBO", chapter, page, "NO_WORK", reasons=["NO_TREATMENT"])
    if not _is_disposable(manga) or not _is_disposable(output_dir):
        return result("COMBO_TURBO", chapter, page, "INVALID",
                      reasons=["DISPOSABLE_ROOT_REQUIRED"])
    prepared, failure = prepare_inputs(manga, provider, chapter, page, level1_path,
                                       solids_path, glass_path, mask_path)
    if failure:
        return failure
    paths = prepared["paths"]
    if "solids" not in paths and "glass" not in paths:
        return _report(prepared, chapter, page, "NO_WORK", ["NO_VALIDATED_CANDIDATE"])
    root, destination = Path(manga).resolve(), Path(output_dir).resolve()
    if destination.is_relative_to(root):
        return result("COMBO_TURBO", chapter, page, "INVALID",
                      reasons=["OUTPUT_INSIDE_MANGA"])
    bundle = destination / f"{chapter}-{Path(page).stem}-combo"
    if bundle.exists():
        return result("COMBO_TURBO", chapter, page, "INVALID",
                      reasons=["OUTPUT_ALREADY_EXISTS"])
    try:
        l1 = _read_rgb(paths["level1"])
        solids = _read_rgb(paths["solids"]) if "solids" in paths else None
        glass = _read_rgb(paths["glass"]) if "glass" in paths else None
        active = _read_mask(paths["mask"]) if glass is not None else None
    except (OSError, ValueError, Image.DecompressionBombError):
        return result("COMBO_TURBO", chapter, page, "INVALID", reasons=["INPUT_IMAGE_INVALID"])
    if any(image is not None and image.shape != l1.shape
           for image in (solids, glass)):
        return result("COMBO_TURBO", chapter, page, "INVALID",
                      reasons=["DIMENSION_MISMATCH"])
    if active is not None and active.shape != l1.shape[:2]:
        return result("COMBO_TURBO", chapter, page, "INVALID",
                      reasons=["DIMENSION_MISMATCH"])
    base = solids if solids is not None else l1
    overlap = _overlap(l1, solids, active) if solids is not None and glass is not None else np.zeros((l1.shape[0], l1.shape[1]), bool)
    count, bounds = _overlap_summary(overlap)
    if count:
        return _report(prepared, chapter, page, "CONFLICT", ["SOLIDS_GLASS_OVERLAP"],
                       overlap_pixels=count, overlap_bounds=bounds)
    final = base.copy()
    if glass is not None:
        final[active] = glass[active]
    error = _invariant_error(final, base, glass, active, l1, solids)
    if error:
        return result("COMBO_TURBO", chapter, page, "INVALID", reasons=[error])
    try:
        _verify_inputs(paths, prepared)
        return _write_bundle(final, destination, bundle, prepared, chapter, page,
                             count, bounds, active)
    except (OSError, ValueError, TypeError):
        return result("COMBO_TURBO", chapter, page, "INVALID", reasons=["WRITE_FAILED"])


def _read_rgb(path):
    with Image.open(path) as image:
        if image.mode not in {"RGB", "RGBA"}:
            raise ValueError("Expected RGB image")
        return np.asarray(image).copy()


def _read_mask(path):
    with Image.open(path) as image:
        return np.asarray(image.convert("L")) > 0


def _is_disposable(path):
    resolved = Path(path).resolve()
    allowed = {Path(tempfile.gettempdir()).resolve(), Path("/tmp").resolve(),
               Path("/private/tmp").resolve()}
    return any(resolved.is_relative_to(root) for root in allowed)


def _overlap(level1, solids, active):
    changed = np.any(solids != level1, axis=2)
    return changed & active


def _overlap_summary(overlap):
    ys, xs = np.nonzero(overlap)
    if not len(xs):
        return 0, None
    return int(len(xs)), {"x": int(xs.min()), "y": int(ys.min()),
                          "width": int(xs.max() - xs.min() + 1),
                          "height": int(ys.max() - ys.min() + 1)}


def _invariant_error(final, base, glass, active, level1, solids):
    if glass is not None:
        if np.any(final[~active] != base[~active]):
            return "PIXELS_OUTSIDE_GLASS_MASK_CHANGED"
        if np.any(final[active] != glass[active]):
            return "GLASS_PIXELS_NOT_PRESERVED"
    if solids is not None and np.any(final[np.any(solids != level1, axis=2)] != solids[np.any(solids != level1, axis=2)]):
        return "SOLIDS_PIXELS_NOT_PRESERVED"
    return None


def _verify_inputs(paths, prepared):
    if {name: sha256(path) for name, path in paths.items()} != prepared["input_hashes"]:
        raise ValueError("Inputs changed while composing")
    check_path = prepared["check_path"]
    current_check = sha256(check_path) if check_path.is_file() else None
    if current_check != prepared["check_manifest_sha256"]:
        raise ValueError("Check changed while composing")
    manifest = prepared["level1_manifest_path"]
    current_manifest = sha256(manifest) if manifest.is_file() else None
    if current_manifest != prepared["level1_manifest_sha256"]:
        raise ValueError("Level I manifest changed while composing")
    for stage, previous in prepared["validations"].items():
        current = validate_page(prepared["root"], prepared["provider"],
                               prepared["chapter"], prepared["page"], stage)
        if current != previous:
            raise ValueError("Stage validation changed while composing")


def _report(prepared, chapter, page, status, reasons, **extra):
    return result("COMBO_TURBO", chapter, page, status, reasons=reasons,
                  source_level1_sha256=prepared["input_hashes"].get("level1"),
                  source_solids_sha256=prepared["input_hashes"].get("solids"),
                  source_glass_sha256=prepared["input_hashes"].get("glass"),
                  mask_sha256=prepared["input_hashes"].get("mask"),
                  check_manifest_sha256=prepared["check_manifest_sha256"],
                  level1_manifest_sha256=prepared["level1_manifest_sha256"],
                  validations=prepared["validations"], **extra)


def _write_bundle(final, destination, bundle, prepared, chapter, page,
                  overlap_pixels, overlap_bounds, active):
    destination.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".combo-", dir=destination))
    try:
        image_path = temporary / "composed.png"
        Image.fromarray(final).save(image_path, format="PNG")
        report = {
            "stage": "COMBO_TURBO", "provider": prepared["provider"],
            "manga": prepared["manga"], "chapter": chapter, "page": page,
            "status": "COMPOSED", "output_scope": "DISPOSABLE_EXPERIMENTAL",
            "promoted": False, "source_level1_sha256": prepared["input_hashes"]["level1"],
            "source_solids_sha256": prepared["input_hashes"].get("solids"),
            "source_glass_sha256": prepared["input_hashes"].get("glass"),
            "level1_manifest_sha256": prepared["level1_manifest_sha256"],
            "mask_sha256": prepared["input_hashes"].get("mask"),
            "check_manifest_sha256": prepared["check_manifest_sha256"],
            "validations": prepared["validations"], "overlap_pixels": overlap_pixels,
            "overlap_bounds": overlap_bounds, "glass_mask_active_pixels":
                int(active.sum()) if active is not None else 0,
            "result_sha256": sha256(image_path),
        }
        (temporary / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
        os.rename(temporary, bundle)
        return {**report, "output_dir": str(bundle), "result_path": str(bundle / "composed.png"),
                "report_path": str(bundle / "report.json"), "reasons": []}
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
