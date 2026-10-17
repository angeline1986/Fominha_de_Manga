"""Validate saved Glass artifacts and report legacy provenance gaps."""
import json
from pathlib import Path

from processamento.unificacao_imagens import image_stitcher as v3
from central_v2.backend.orchestration.textoff_special.artifacts import sha256
from central_v2.backend.orchestration.textoff_merged.auto_cleaner_check_manifest import _read_check_manifest, manifest_path
from central_v2.backend.orchestration.textoff_merged.artifact_paths import artifact_file, json_file
from central_v2.backend.orchestration.textoff_merged.consolidated import _valid_level2
from central_v2.backend.orchestration.textoff_merged.manifests import (
    _manifest_matches_merge, _stage_manifest, _stage_manifest_sha256,
)
from central_v2.backend.orchestration.textoff_merged.stages import LEVEL1, LEVEL2, stage_chapter

from .models import check_digest_field, image_size, is_sha256, result, safe_file, valid_chapter_id, valid_page_id
from .glass_provenance import (
    report_page_matches, safe_stage_artifact, validate_level1_dependencies,
    validate_protection_source,
)

def validate_glass_page(manga: Path, provider: str, chapter: str, page: str) -> dict:
    """Validate one Glass page; legacy Check lineage is explicitly unverified."""
    if not valid_chapter_id(chapter):
        return result("GLASS", chapter, page, "INVALID", reasons=["INVALID_CHAPTER"])
    if not valid_page_id(page):
        return result("GLASS", chapter, page, "INVALID", reasons=["INVALID_PAGE_ID"])
    root = Path(manga).resolve()
    try:
        folder = stage_chapter(root, LEVEL2, chapter)
    except (OSError, RuntimeError, ValueError):
        return result("GLASS", chapter, page, "UNVERIFIED",
                      reasons=["AUTHORITY_UNAVAILABLE"])
    if folder.is_symlink() or not folder.resolve().is_relative_to(root):
        return result("GLASS", chapter, page, "INVALID", reasons=["PATH_OUTSIDE_ROOT"])
    pathname = json_file(folder, "clean-manifest.json")
    if not pathname.is_file():
        partial = folder.exists() and any(folder.iterdir())
        return result("GLASS", chapter, page, "INVALID" if partial else "MISSING",
                      reasons=["MANIFEST_INVALID" if partial else "ARTIFACT_NOT_FOUND"])
    try:
        manifest = json.loads(pathname.read_text(encoding="utf-8"))
        manifest_hash = sha256(pathname)
    except (OSError, ValueError, TypeError):
        return result("GLASS", chapter, page, "INVALID", reasons=["MANIFEST_INVALID"])
    if not isinstance(manifest, dict):
        return result("GLASS", chapter, page, "INVALID", manifest=manifest_hash,
                      reasons=["MANIFEST_INVALID"])
    if ("provenance_version" in manifest
            and manifest.get("provenance_version") != 1):
        return result("GLASS", chapter, page, "INVALID", manifest=manifest_hash,
                      reasons=["MANIFEST_INVALID"])
    candidates = manifest.get("candidate_source_artifacts")
    if not isinstance(candidates, list) or page not in candidates:
        return result("GLASS", chapter, page, "MISSING", manifest=manifest_hash,
                      reasons=["PAGE_NOT_GLASS_CANDIDATE"])
    try:
        level1 = _stage_manifest(root, LEVEL1, chapter)
        level1_hash = _stage_manifest_sha256(root, LEVEL1, chapter)
        merge_matches = _manifest_matches_merge(level1, root, chapter)
    except (OSError, RuntimeError, ValueError, TypeError):
        return result("GLASS", chapter, page, "UNVERIFIED", manifest=manifest_hash,
                      reasons=["AUTHORITY_UNAVAILABLE"])
    if not merge_matches:
        return result("GLASS", chapter, page, "STALE", manifest=manifest_hash,
                      reasons=["SOURCE_HASH_MISMATCH"])
    valid, valid_folder, valid_hash = _valid_level2(root, chapter, level1, level1_hash)
    if valid_hash != manifest_hash:
        return result("GLASS", chapter, page, "INVALID", manifest=manifest_hash,
                      reasons=["MANIFEST_INVALID"])
    if valid is None or valid_folder is None:
        old_level1_hash = manifest.get("source_level1_manifest_sha256")
        status, reason = (("STALE", "SOURCE_HASH_MISMATCH") if old_level1_hash != level1_hash
                          else ("INVALID", "MANIFEST_INVALID"))
        return result("GLASS", chapter, page, status, manifest=manifest_hash,
                      reasons=[reason])
    manifest = valid
    for key in ("check_sha256", "source_check_manifest_sha256"):
        if manifest.get(key) is not None and not is_sha256(manifest[key]):
            return result("GLASS", chapter, page, "INVALID", integrity=True,
                          manifest=valid_hash, reasons=["MANIFEST_INVALID"])
    source_check = manifest.get("source_check")
    if source_check is not None and (
            not isinstance(source_check, dict)
            or (source_check.get("sha256") is not None
                and not is_sha256(source_check["sha256"]))):
        return result("GLASS", chapter, page, "INVALID", integrity=True,
                      manifest=valid_hash, reasons=["MANIFEST_INVALID"])
    modern_provenance = manifest.get("provenance_version") == 1
    digest = check_digest_field(manifest)
    check_path = manifest_path(root, chapter)
    current_check_hash = sha256(check_path) if check_path.is_file() else None
    if check_path.is_file():
        try:
            _read_check_manifest(check_path, {"provider": provider, "obra": root.name,
                                              "capitulo": chapter})
        except (OSError, ValueError, TypeError, KeyError):
            return result("GLASS", chapter, page, "INVALID", integrity=True,
                          manifest=valid_hash, reasons=["MANIFEST_INVALID"])
    if not modern_provenance and digest and current_check_hash and digest != current_check_hash:
        return result("GLASS", chapter, page, "STALE", integrity=True,
                      manifest=valid_hash, reasons=["CHECK_CHANGED"])
    if not modern_provenance and digest and not current_check_hash:
        return result("GLASS", chapter, page, "STALE", integrity=True,
                      manifest=valid_hash, reasons=["CHECK_CHANGED"])
    row = next((item for item in manifest.get("page_results", [])
                if isinstance(item, dict) and item.get("source") == page), None)
    if row is None:
        return result("GLASS", chapter, page, "INVALID", integrity=True,
                      manifest=valid_hash, reasons=["MANIFEST_INVALID"])
    protection_valid = False
    if modern_provenance:
        if not report_page_matches(valid_folder, page, row):
            return result("GLASS", chapter, page, "INVALID", integrity=True,
                          manifest=valid_hash, reasons=["MANIFEST_INVALID"])
        protection = validate_protection_source(root, provider, chapter, page, row)
        if protection:
            status, reasons = protection
            return result("GLASS", chapter, page, status, integrity=True,
                          manifest=valid_hash, reasons=reasons)
        protection_valid = True
    try:
        merge_dir = v3.merge_output_dir(root / "IMG" / chapter)
        if not merge_dir.resolve().is_relative_to(root):
            return result("GLASS", chapter, page, "INVALID", integrity=True,
                          manifest=valid_hash, reasons=["PATH_OUTSIDE_ROOT"])
        source = safe_file(merge_dir, page)
        level1_dir = stage_chapter(root, LEVEL1, chapter)
        if level1_dir.is_symlink() or not level1_dir.resolve().is_relative_to(root):
            return result("GLASS", chapter, page, "INVALID", integrity=True,
                          manifest=valid_hash, reasons=["PATH_OUTSIDE_ROOT"])
        if modern_provenance:
            dependency = validate_level1_dependencies(level1_dir, page, row)
            if dependency:
                status, reasons = dependency
                return result("GLASS", chapter, page, status, integrity=True,
                              manifest=valid_hash, reasons=reasons)
        level1_image = safe_stage_artifact(level1_dir, row.get("level1_clean"), "clean")
        if level1_image is None:
            return result("GLASS", chapter, page, "STALE", integrity=True,
                          manifest=valid_hash, reasons=["SOURCE_HASH_MISMATCH"])
        mask = safe_stage_artifact(valid_folder, row.get("mask"), "mask")
        if mask is None:
            return result("GLASS", chapter, page, "INVALID", integrity=True,
                          manifest=valid_hash, reasons=["ARTIFACT_NOT_FOUND"])
        clean = safe_stage_artifact(valid_folder, row.get("clean"), "clean") if row.get("clean") else level1_image
        actual = {"source": sha256(source), "level1": sha256(level1_image),
                  "result": sha256(clean), "mask": sha256(mask)}
        sizes = {image_size(source), image_size(level1_image), image_size(clean), image_size(mask)}
        if len(sizes) != 1:
            return result("GLASS", chapter, page, "INVALID", integrity=True,
                          artifact=actual["result"], mask=actual["mask"], manifest=valid_hash,
                          reasons=["DIMENSION_MISMATCH"])
    except (OSError, ValueError, TypeError, KeyError):
        return result("GLASS", chapter, page, "INVALID", integrity=True,
                      manifest=valid_hash, reasons=["ARTIFACT_NOT_FOUND"])
    reasons = []
    expected = {
        "source": row.get("source_sha256"),
        "level1": row.get("level1_sha256"),
        "result": row.get("result_sha256"),
        "mask": row.get("mask_sha256"),
    }
    for key, value in expected.items():
        if not isinstance(value, str):
            reasons.append({"source": "SOURCE_HASH_NOT_RECORDED", "level1": "LEVEL1_HASH_NOT_RECORDED",
                            "result": "ARTIFACT_HASH_NOT_RECORDED", "mask": "MASK_HASH_NOT_RECORDED"}[key])
        elif not is_sha256(value):
            return result("GLASS", chapter, page, "INVALID", integrity=True,
                          manifest=valid_hash, artifact=actual["result"], mask=actual["mask"],
                          reasons=["MANIFEST_INVALID"])
        elif value != actual[key]:
            return result("GLASS", chapter, page,
                          "STALE" if key in {"source", "level1"} else "INVALID", integrity=True,
                          manifest=valid_hash, artifact=actual["result"], mask=actual["mask"],
                          reasons=["SOURCE_HASH_MISMATCH" if key in {"source", "level1"}
                                   else "MASK_HASH_MISMATCH" if key == "mask"
                                   else "ARTIFACT_HASH_MISMATCH"])
    check_verified = protection_valid or bool(digest and current_check_hash and digest == current_check_hash)
    if not check_verified and not modern_provenance:
        reasons.append("CHECK_HASH_NOT_RECORDED" if current_check_hash
                       else "CHECK_MANIFEST_MISSING")
    reusable = not reasons
    if (sha256(pathname) != manifest_hash
            or (check_path.is_file() and sha256(check_path) != current_check_hash)
            or _stage_manifest_sha256(root, LEVEL1, chapter) != level1_hash
            or sha256(source) != actual["source"]):
        return result("GLASS", chapter, page, "INVALID", integrity=True,
                      manifest=valid_hash, artifact=actual["result"], mask=actual["mask"],
                      reasons=["MANIFEST_INVALID"])
    if modern_provenance:
        protection = validate_protection_source(root, provider, chapter, page, row)
        if protection:
            status, reasons = protection
            return result("GLASS", chapter, page, status, integrity=True,
                          manifest=valid_hash, reasons=reasons)
    return result("GLASS", chapter, page, "REUSABLE" if reusable else "UNVERIFIED",
                  integrity=True, check=check_verified, artifact=actual["result"],
                  mask=actual["mask"], manifest=valid_hash, reasons=reasons,
                  source_sha256=actual["source"], level1_sha256=actual["level1"])
