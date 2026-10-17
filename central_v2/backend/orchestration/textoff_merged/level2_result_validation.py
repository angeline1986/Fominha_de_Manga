"""Validate Level II page outputs against their manifest report."""
import json
from pathlib import Path

from .artifact_paths import artifact_file, artifact_ref


def _valid_level2_page_results(folder, level1_folder, manifest, page_results,
                               candidates, changed_sources, unchanged_sources, clean_names):
    rows = {item.get("source"): item for item in page_results}
    clean_by_source = {
        Path(source).stem + Path(source).suffix:
        artifact_ref("clean", Path(source).stem + "_clean" + Path(source).suffix)
        for source in candidates
    }
    clean_set = set(clean_names)
    masks = manifest.get("mask_artifacts")
    if not isinstance(masks, list) or len(masks) != len(candidates) or len(masks) != len(set(masks)):
        return False
    row_masks = []
    for source in candidates:
        row = rows[source]
        expected_clean = clean_by_source[Path(source).name]
        if row.get("level1_clean") != expected_clean:
            return False
        if artifact_file(level1_folder, row.get("level1_clean"), "clean") is None:
            return False
        mask = row.get("mask")
        if artifact_file(folder, mask, "mask") is None:
            return False
        row_masks.append(mask)
        pixels = row.get("changed_pixels")
        if not isinstance(pixels, int) or isinstance(pixels, bool) or pixels < 0:
            return False
        mask_pixels = row.get("mask_pixels")
        if not isinstance(mask_pixels, int) or isinstance(mask_pixels, bool) or mask_pixels < 0:
            return False
        clean = row.get("clean")
        if source in changed_sources:
            if clean != expected_clean or clean not in clean_set or pixels <= 0:
                return False
        elif source in unchanged_sources:
            if clean is not None or pixels != 0:
                return False
        else:
            return False
    if set(row_masks) != set(masks):
        return False
    report_ref = manifest.get("report")
    report_path = artifact_file(folder, report_ref, "json")
    if report_path is None:
        return False
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return False
    report_pages = report.get("pages")
    if (report.get("integrity_ok") is not True
            or report.get("pages_analyzed") != len(candidates)
            or not isinstance(report_pages, list)
            or len(report_pages) != len(candidates)):
        return False
    report_by_source = {item.get("source"): item for item in report_pages if isinstance(item, dict)}
    if len(report_by_source) != len(candidates) or set(report_by_source) != set(candidates):
        return False
    for source in candidates:
        row, report_row = rows[source], report_by_source[source]
        fields = ("clean", "level1_clean", "mask", "changed_pixels", "mask_pixels")
        if manifest.get("provenance_version") == 1:
            fields += ("source_sha256", "level1_sha256", "result_sha256", "mask_sha256",
                       "level1_report_sha256", "level1_mask_sha256", "deferred_mask_sha256",
                       "protection_source", "protected_occurrence_ids", "protected_types_applied",
                       "protected_occurrences", "protected_types")
        if any(report_row.get(key) != row.get(key) for key in fields):
            return False
        if report_row.get("changed_outside_mask") != 0:
            return False
    return True
