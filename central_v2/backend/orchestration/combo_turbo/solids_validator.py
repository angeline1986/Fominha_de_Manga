"""Validate a saved Sólidos preview without executing or promoting it."""
import json
from pathlib import Path

from central_v2.backend.orchestration.textoff_special.artifacts import sha256
from central_v2.backend.orchestration.textoff_merged.auto_cleaner_check_manifest import manifest_path
from central_v2.backend.orchestration.textoff_merged.solid_stage import (
    STAGE, rows_for, source_for,
)
from central_v2.backend.orchestration.textoff_merged.stages import stage_chapter

from .models import image_size, is_sha256, result, safe_file, valid_chapter_id, valid_page_id


def validate_solids_page(manga: Path, provider: str, chapter: str, page: str) -> dict:
    """Return artifact integrity and current Check/source compatibility."""
    if not valid_chapter_id(chapter):
        return result("SOLIDOS", chapter, page, "INVALID", reasons=["INVALID_CHAPTER"])
    if not valid_page_id(page):
        return result("SOLIDOS", chapter, page, "INVALID", reasons=["INVALID_PAGE_ID"])
    if Path(page).suffix.lower() != ".png":
        return result("SOLIDOS", chapter, page, "INVALID", reasons=["INVALID_PAGE_ID"])
    root = Path(manga).resolve()
    folder = stage_chapter(root, STAGE, chapter, read_legacy=False)
    if folder.is_symlink() or not folder.resolve().is_relative_to(root):
        return result("SOLIDOS", chapter, page, "INVALID", reasons=["PATH_OUTSIDE_ROOT"])
    manifest_pathname = folder / "solid-white-manifest.json"
    if not manifest_pathname.is_file():
        partial = folder.exists() and any(folder.iterdir())
        return result("SOLIDOS", chapter, page, "INVALID" if partial else "MISSING",
                      reasons=["MANIFEST_INVALID" if partial else "ARTIFACT_NOT_FOUND"])

    try:
        manifest = json.loads(manifest_pathname.read_text(encoding="utf-8"))
        digest = sha256(manifest_pathname)
    except (OSError, ValueError, TypeError):
        return result("SOLIDOS", chapter, page, "INVALID", reasons=["MANIFEST_INVALID"])
    if not _valid_manifest(manifest, provider, root.name, chapter):
        return result("SOLIDOS", chapter, page, "INVALID", manifest=digest,
                      reasons=["MANIFEST_INVALID"])
    row = next((item for item in manifest["pages"] if item.get("page") == page), None)
    if row is None:
        return result("SOLIDOS", chapter, page, "MISSING", manifest=digest,
                      reasons=["ARTIFACT_NOT_FOUND"])

    check_path = manifest_path(root, chapter)
    if not check_path.is_file():
        return result("SOLIDOS", chapter, page, "UNVERIFIED", manifest=digest,
                      reasons=["CHECK_MANIFEST_MISSING"])
    document = {"provider": provider, "obra": root.name, "capitulo": chapter}
    try:
        approved, check_hash = rows_for(root, document, chapter)
    except (OSError, ValueError, TypeError, KeyError):
        return result("SOLIDOS", chapter, page, "INVALID", manifest=digest,
                      reasons=["MANIFEST_INVALID"])
    current_ids = {item.get("id") for item in approved if item.get("page") == page}
    current_count = sum(item.get("page") == page for item in approved)
    saved_rows = [item for item in manifest["regions"] if item.get("page") == page]
    saved_ids = {item.get("id") for item in saved_rows}
    if manifest["check_sha256"] != check_hash:
        return result("SOLIDOS", chapter, page, "STALE", manifest=digest,
                      reasons=["CHECK_CHANGED"])
    if (not current_ids or len(current_ids) != current_count
            or len(saved_ids) != len(saved_rows) or current_ids != saved_ids):
        return result("SOLIDOS", chapter, page, "INVALID", check=True,
                      manifest=digest, reasons=["MANIFEST_INVALID"])

    try:
        source = source_for(root, chapter, page)
        source_hash = sha256(source)
        if source_hash != row.get("source_sha256"):
            return result("SOLIDOS", chapter, page, "STALE", check=True,
                          manifest=digest, reasons=["SOURCE_HASH_MISMATCH"])
        output = safe_file(folder, f"clean/{Path(page).stem}_clean.png")
        mask = safe_file(folder, f"mask/{Path(page).stem}_mask.png")
        output_hash, mask_hash = sha256(output), sha256(mask)
        if output_hash != row.get("result_sha256"):
            return result("SOLIDOS", chapter, page, "INVALID", check=True,
                          manifest=digest, artifact=output_hash, mask=mask_hash,
                          reasons=["ARTIFACT_HASH_MISMATCH"])
        if mask_hash != row.get("mask_sha256"):
            return result("SOLIDOS", chapter, page, "INVALID", check=True,
                          manifest=digest, artifact=output_hash, mask=mask_hash,
                          reasons=["MASK_HASH_MISMATCH"])
        dimensions = {image_size(source), image_size(output), image_size(mask)}
        if len(dimensions) != 1:
            return result("SOLIDOS", chapter, page, "INVALID", check=True,
                          manifest=digest, artifact=output_hash, mask=mask_hash,
                          reasons=["DIMENSION_MISMATCH"])
    except (OSError, ValueError, TypeError, KeyError):
        return result("SOLIDOS", chapter, page, "INVALID", check=True,
                      manifest=digest, reasons=["ARTIFACT_NOT_FOUND"])
    return result("SOLIDOS", chapter, page, "REUSABLE", integrity=True,
                  check=True, artifact=output_hash, mask=mask_hash, manifest=digest,
                  preview_only=True, reasons=[])


def _valid_manifest(value, provider, manga, chapter):
    return (isinstance(value, dict) and value.get("schema") == "textoff_solid_stage_v1"
            and value.get("provider") == provider and value.get("manga") == manga
            and value.get("chapter") == chapter and value.get("preview_only") is True
            and is_sha256(value.get("check_sha256"))
            and isinstance(value.get("pages"), list)
            and isinstance(value.get("regions"), list)
            and all(isinstance(item, dict) for item in value["pages"])
            and all(valid_page_id(item.get("page")) for item in value["pages"])
            and all(is_sha256(item.get(key)) for item in value["pages"]
                    for key in ("source_sha256", "result_sha256", "mask_sha256"))
            and all(isinstance(item, dict) for item in value["regions"])
            and all(isinstance(item.get("id"), str) and item.get("id")
                    and isinstance(item.get("page"), str) for item in value["regions"])
            and len({item["id"] for item in value["regions"]}) == len(value["regions"])
            and len({item.get("page") for item in value["pages"]}) == len(value["pages"]))
