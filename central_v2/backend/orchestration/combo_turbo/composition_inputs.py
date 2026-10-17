"""Resolve and validate explicit inputs for an isolated composition."""
from pathlib import Path

from central_v2.backend.orchestration.textoff_special.artifacts import sha256
from central_v2.backend.orchestration.textoff_merged.auto_cleaner_check_manifest import manifest_path
from central_v2.backend.orchestration.textoff_merged.artifact_paths import json_file
from central_v2.backend.orchestration.textoff_merged.stages import LEVEL1, stage_chapter

from .models import image_size, result
from .validation import validate_page


def prepare_inputs(manga, provider, chapter, page, level1_path, solids_path,
                   glass_path, mask_path):
    """Return validated paths and provenance, or a non-success report."""
    if level1_path is None:
        return None, result("COMBO_TURBO", chapter, page, "INVALID",
                            reasons=["INPUT_MISSING"])
    root = Path(manga).resolve()
    paths = {"level1": Path(level1_path)}
    if bool(glass_path) != bool(mask_path):
        return None, result("COMBO_TURBO", chapter, page, "INVALID",
                            reasons=["GLASS_RESULT_AND_MASK_REQUIRED_TOGETHER"])
    for name, path in (("level1", paths["level1"]), ("solids", solids_path),
                       ("glass", glass_path), ("mask", mask_path)):
        if path is None:
            continue
        resolved = Path(path).resolve()
        if not resolved.is_relative_to(root) or not resolved.is_file():
            return None, result("COMBO_TURBO", chapter, page, "INVALID",
                                reasons=["INPUT_MISSING" if not resolved.is_file()
                                         else "INPUT_OUTSIDE_MANGA"])
        paths[name] = resolved
    try:
        l1_dir = stage_chapter(root, LEVEL1, chapter)
        expected_l1 = (l1_dir / "clean" / f"{Path(page).stem}_clean.png").resolve()
        if paths["level1"] != expected_l1:
            return None, result("COMBO_TURBO", chapter, page, "INVALID",
                                reasons=["LEVEL1_REFERENCE_MISMATCH"])
        sizes = {name: image_size(path) for name, path in paths.items()}
        if len(set(sizes.values())) != 1:
            return None, result("COMBO_TURBO", chapter, page, "INVALID",
                                reasons=["DIMENSION_MISMATCH"])
    except (OSError, ValueError, RuntimeError):
        return None, result("COMBO_TURBO", chapter, page, "INVALID",
                            reasons=["INPUT_IMAGE_INVALID"])

    validations = {}
    for stage, artifact in (("SOLIDOS", solids_path), ("GLASS", glass_path)):
        if artifact is None:
            continue
        validation = validate_page(root, provider, chapter, page, stage)
        validations[stage] = validation
        if stage == "GLASS" and validation["status"] == "MISSING" and (
                "PAGE_NOT_GLASS_CANDIDATE" in validation["reasons"]):
            paths.pop("glass", None)
            paths.pop("mask", None)
            continue
        if validation["status"] != "REUSABLE":
            return None, result("COMBO_TURBO", chapter, page, validation["status"],
                                reasons=[f"{stage}_{reason}" for reason in validation["reasons"]],
                                validation=validation)
        if not validation.get("integrity_ok") or not validation.get("check_verified"):
            return None, result("COMBO_TURBO", chapter, page, "UNVERIFIED",
                                reasons=[f"{stage}_PROVENANCE_INCOMPLETE"],
                                validation=validation)
        key = "artifact_sha256"
        if sha256(paths["solids" if stage == "SOLIDOS" else "glass"]) != validation[key]:
            return None, result("COMBO_TURBO", chapter, page, "INVALID",
                                reasons=[f"{stage}_HASH_MISMATCH"], validation=validation)
        if stage == "GLASS" and sha256(paths["mask"]) != validation["mask_sha256"]:
            return None, result("COMBO_TURBO", chapter, page, "INVALID",
                                reasons=["GLASS_MASK_HASH_MISMATCH"], validation=validation)

    try:
        check_path = manifest_path(root, chapter)
        check_hash = sha256(check_path) if check_path.is_file() else None
        level1_manifest = json_file(paths["level1"].parent.parent, "clean-manifest.json")
        level1_manifest_hash = sha256(level1_manifest) if level1_manifest.is_file() else None
        before = {name: sha256(path) for name, path in paths.items()}
    except OSError:
        return None, result("COMBO_TURBO", chapter, page, "INVALID",
                            reasons=["INPUT_HASH_UNAVAILABLE"])
    return ({"paths": paths, "validations": validations, "sizes": sizes,
             "input_hashes": before, "check_manifest_sha256": check_hash,
             "level1_manifest_path": level1_manifest,
             "level1_manifest_sha256": level1_manifest_hash,
             "check_path": check_path, "root": root, "chapter": chapter,
             "page": page, "provider": provider, "manga": root.name}, None)
