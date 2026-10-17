"""Validate Level II lineage back to the protection authority used at runtime."""
import json

from central_v2.backend.orchestration.textoff_merged.level2_manual_protection import (
    load_level1_protection_context,
)
from central_v2.backend.orchestration.textoff_merged.artifact_paths import (
    artifact_file, json_file,
)
from central_v2.backend.orchestration.textoff_special.artifacts import sha256

from .models import is_sha256


def safe_stage_artifact(folder, reference, kind):
    path = artifact_file(folder, reference, kind)
    if path is None or not path.resolve().is_relative_to(folder.resolve()):
        return None
    return path


def report_page_matches(folder, page, row):
    path = json_file(folder, "level2-transparent-report.json")
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return False
    source_row = next((item for item in report.get("pages", [])
                       if isinstance(item, dict) and item.get("source") == page), None)
    fields = ("source_sha256", "level1_sha256", "result_sha256", "mask_sha256",
              "level1_report_sha256", "level1_mask_sha256", "deferred_mask_sha256",
              "protection_source", "protected_occurrence_ids", "protected_types_applied",
              "protected_occurrences", "protected_types")
    return source_row is not None and all(source_row.get(key) == row.get(key) for key in fields)


def validate_level1_dependencies(folder, page, row):
    path = json_file(folder, "level1-balloon-report.json")
    if path.is_symlink() or not path.resolve().is_relative_to(folder.resolve()):
        return "INVALID", ["PATH_OUTSIDE_ROOT"]
    if not path.is_file():
        return "STALE", ["SOURCE_HASH_MISMATCH"]
    if sha256(path) != row.get("level1_report_sha256"):
        return "STALE", ["SOURCE_HASH_MISMATCH"]
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return "INVALID", ["MANIFEST_INVALID"]
    source = next((item for item in report.get("pages", [])
                   if isinstance(item, dict) and item.get("source") == page), None)
    if source is None:
        return "STALE", ["SOURCE_HASH_MISMATCH"]
    label = safe_stage_artifact(folder, source.get("transparent_mask_artifact"), "mask")
    if label is None or sha256(label) != row.get("level1_mask_sha256"):
        return "STALE", ["SOURCE_HASH_MISMATCH"]
    deferred_ref = source.get("deferred_text_mask_artifact")
    deferred = safe_stage_artifact(folder, deferred_ref, "mask") if deferred_ref else None
    actual = sha256(deferred) if deferred else None
    if deferred_ref and deferred is None:
        return "STALE", ["SOURCE_HASH_MISMATCH"]
    if actual != row.get("deferred_mask_sha256"):
        return "STALE", ["SOURCE_HASH_MISMATCH"]
    return None


def validate_protection_source(root, provider, chapter, page, row):
    saved = row.get("protection_source")
    if (not isinstance(saved, dict)
            or saved.get("kind") not in {"CHECK", "RESIDUE_OCCURRENCES"}
            or not isinstance(saved.get("path"), str)
            or (saved.get("sha256") is not None and not is_sha256(saved["sha256"]))):
        return "INVALID", ["MANIFEST_INVALID"]
    try:
        protections, current = load_level1_protection_context(
            root, provider, root.name, chapter)
    except (OSError, ValueError, TypeError, KeyError):
        return "INVALID", ["PROTECTION_SOURCE_INVALID"]
    if saved != current:
        return "STALE", ["PROTECTION_SOURCE_CHANGED"]
    expected = protections.get(page, [])
    ids = sorted(item["id"] for item in expected if isinstance(item.get("id"), str))
    types = sorted({item["tipo"] for item in expected if isinstance(item.get("tipo"), str)})
    if (row.get("protected_occurrence_ids") != ids
            or row.get("protected_types_applied") != types
            or row.get("protected_occurrences") != len(expected)
            or row.get("protected_types") != types):
        return "INVALID", ["PROTECTION_APPLICATION_MISMATCH"]
    return None
