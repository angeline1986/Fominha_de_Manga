"""Compatibility validation for legacy Level II manifests."""
import json
from pathlib import Path

from .artifact_paths import artifact_file
from .level2_vision import ALGORITHM as LEVEL2_ALGORITHM
from .stages import LEVEL1


def _source_from_clean(reference):
    name = Path(str(reference)).name
    path = Path(name)
    suffix = path.suffix
    stem = path.stem
    return stem[:-6] + suffix if stem.endswith("_clean") else name


def _changed_source_set(manifest):
    changed = manifest.get("changed_source_artifacts")
    if isinstance(changed, list):
        return set(changed)
    return set(manifest.get("candidate_source_artifacts", []))


def _valid_legacy_level2(folder, level1_folder, level1, level1_hash, manifest):
    candidates = manifest.get("candidate_source_artifacts")
    outputs = manifest.get("clean_artifacts")
    changed = manifest.get("changed_artifacts", outputs)
    if (manifest.get("integrity_ok") is not True
            or manifest.get("algorithm") != LEVEL2_ALGORITHM
            or manifest.get("source_stage") not in {LEVEL1, "MERGED_NIVEL_I"}
            or manifest.get("source_level1_manifest_sha256") != level1_hash
            or manifest.get("source_artifacts") != level1.get("source_artifacts")
            or not isinstance(candidates, list) or len(candidates) != len(set(candidates))
            or int(manifest.get("pages_total") or 0) != len(candidates)
            or not set(candidates).issubset(set(level1.get("source_artifacts", [])))
            or not isinstance(outputs, list) or len(outputs) != len(candidates)
            or len(outputs) != len(set(outputs)) or not isinstance(changed, list)
            or set(changed) != set(outputs) or int(manifest.get("outputs_total") or 0) != len(outputs)):
        return False
    expected_names = {Path(source).stem + "_clean" + Path(source).suffix for source in candidates}
    if ({Path(name).name for name in outputs} != expected_names
            or any(artifact_file(folder, name, "clean") is None for name in outputs)):
        return False
    expected_level1 = [item for item in level1.get("clean_artifacts", [])
                       if _source_from_clean(item) in candidates]
    if manifest.get("source_level1_artifacts") not in (None, expected_level1):
        return False
    report_path = artifact_file(folder, manifest.get("report"), "json")
    if report_path is None:
        return False
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return False
    pages = report.get("pages")
    if (report.get("integrity_ok") is not True or report.get("pages_analyzed") != len(candidates)
            or not isinstance(pages, list) or len(pages) != len(candidates)):
        return False
    by_source = {item.get("source"): item for item in pages if isinstance(item, dict)}
    if len(by_source) != len(candidates) or set(by_source) != set(candidates):
        return False
    masks = manifest.get("mask_artifacts")
    if not isinstance(masks, list) or len(masks) != len(candidates) or len(masks) != len(set(masks)):
        return False
    for source in candidates:
        row = by_source[source]
        clean = artifact_ref("clean", Path(source).stem + "_clean" + Path(source).suffix)
        level1_clean = clean
        if (row.get("clean") != clean or row.get("changed_outside_mask") != 0
                or artifact_file(folder, clean, "clean") is None
                or artifact_file(level1_folder, level1_clean, "clean") is None
                or artifact_file(folder, row.get("mask"), "mask") is None):
            return False
    return set(masks) == {row.get("mask") for row in pages}
