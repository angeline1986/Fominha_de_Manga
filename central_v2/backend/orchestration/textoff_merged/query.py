"""Build read-only TextOff Merged worklist projections."""
import json
from pathlib import Path

from processamento.unificacao_imagens import image_stitcher as v3
from central_v2.backend.state.sorting import natural_sort_key

from .manifests import (
    _clean_manifest, _deferred_text_masks_ready, _listing_merge_artifacts,
    _manifest_matches_merge, _stage_manifest, _stage_manifest_sha256,
    _transparent_masks_ready,
)
from .artifact_paths import artifact_file
from .level2_vision import ALGORITHM
from .stages import LEVEL1, LEVEL2, stage_chapter

def query_merged(manga: Path) -> dict:
    """Project official MERGE availability and current TextOff manifests."""
    rows = []
    root = manga / "IMG"
    chapters = sorted(
        (path for path in root.iterdir() if path.is_dir()),
        key=lambda path: natural_sort_key(path.name),
    ) if root.is_dir() else []
    for chapter in chapters:
        files = _listing_merge_artifacts(chapter)
        merged = bool(files)
        manifest = _clean_manifest(manga, chapter.name)
        expected = [path.name for path in files]
        processed = (
            manifest.get("source_stage") == "MERGE"
            and manifest.get("integrity_ok") is True
            and manifest.get("source_artifacts") == expected
            and manifest.get("outputs_total") == len(expected)
        )
        rows.append({
            "chapter": chapter.name,
            "merge_valid": merged,
            "merge_count": len(files),
            "cleaned": processed,
            "clean_count": int(manifest.get("outputs_total") or 0),
            "selectable": merged and bool(files),
        })
    return {"chapters": rows, "total": len(rows)}


def query_merged_level1(manga: Path) -> dict:
    """List dedicated Merged Nível I outputs without mixing legacy results."""
    result = query_merged(manga)
    for row in result["chapters"]:
        manifest = _stage_manifest(manga, LEVEL1, row["chapter"])
        valid = _manifest_matches_merge(manifest, manga, row["chapter"])
        level1 = manifest.get("level1") if isinstance(manifest.get("level1"), dict) else {}
        report_name = level1.get("report")
        chapter_dir = stage_chapter(manga, LEVEL1, row["chapter"])
        candidate_pages = []
        report_path = artifact_file(chapter_dir, report_name, "json")
        if report_path is not None:
            try:
                report = json.loads(report_path.read_text(encoding="utf-8"))
                candidate_pages = [
                    page["source"] for page in report.get("pages", [])
                    if isinstance(page, dict) and isinstance(page.get("source"), str)
                    and (page.get("transparent_balloons") or page.get("transparent_components_deferred"))
                ]
            except (OSError, ValueError, TypeError):
                candidate_pages = []
        row.update({
            "cleaned": valid,
            "clean_count": int(manifest.get("outputs_total") or 0) if valid else 0,
            "transparent_balloons": int(level1.get("transparent_balloons_total") or 0),
            "transparent_pages": candidate_pages,
            "transparent_page_count": len(candidate_pages),
            "deferred_components": int(level1.get("transparent_components_deferred") or 0),
            "transparent_masks_ready": _transparent_masks_ready(manga, row["chapter"], manifest),
            "deferred_text_masks_ready": _deferred_text_masks_ready(manga, row["chapter"], manifest),
            "selectable": row["merge_valid"],
        })
    return result


def query_merged_level2(manga: Path) -> dict:
    """List Nível I chapters and report which have deferred transparent cases."""
    result = query_merged_level1(manga)
    for row in result["chapters"]:
        if not row["merge_valid"]:
            row["level2_status"] = "invalid_merge"
        elif (not row["cleaned"] or not row["transparent_masks_ready"]
              or not row["deferred_text_masks_ready"]):
            row["level2_status"] = "missing_level1"
        elif row["transparent_balloons"] or row["deferred_components"]:
            candidate_pages = row.get("transparent_pages", [])
            previous = _stage_manifest(manga, LEVEL2, row["chapter"])
            level1 = _stage_manifest(manga, LEVEL1, row["chapter"])
            previous_dir = stage_chapter(manga, LEVEL2, row["chapter"])
            outputs = previous.get("clean_artifacts")
            expected_outputs = previous.get("source_level1_artifacts")
            expected_pages = len(candidate_pages)
            if not isinstance(outputs, list):
                outputs = []
            if not isinstance(expected_outputs, list):
                expected_outputs = []
            previous_valid = (
                previous.get("integrity_ok") is True
                and previous.get("algorithm") == ALGORITHM
                and previous.get("candidate_source_artifacts", candidate_pages) == candidate_pages
                and (expected_outputs == [
                    item for item in level1.get("clean_artifacts", [])
                    if _source_from_clean(item) in candidate_pages
                ] or (not previous.get("candidate_source_artifacts")
                     and expected_outputs == level1.get("clean_artifacts")))
                and previous.get("source_level1_manifest_sha256") == _stage_manifest_sha256(
                    manga, LEVEL1, row["chapter"]
                )
                and previous.get("source_artifacts", level1.get("source_artifacts")) == level1.get("source_artifacts")
                and len(outputs) == int(previous.get("outputs_total") or 0)
                and int(previous.get("pages_total") or 0) == expected_pages
                and len(outputs) == expected_pages
                and all(artifact_file(previous_dir, item, "clean") is not None for item in outputs)
            )
            outcome = previous.get("outcome")
            row["level2_status"] = (
                ("processed" if outcome == "visual_changes" else "no_change")
                if previous_valid else "pending"
            )
            row["level2_pages_with_text"] = int(previous.get("pages_with_text") or 0) if previous_valid else 0
            row["level2_changed_pixels"] = int(previous.get("changed_pixels") or 0) if previous_valid else 0
            row["level2_candidate_pages"] = candidate_pages
        else:
            row["level2_status"] = "no_candidates"
        row["selectable"] = row["level2_status"] == "pending"
    return result


def _source_from_clean(reference):
    name = Path(str(reference)).name
    path = Path(name)
    suffix = path.suffix
    stem = path.stem
    return stem[:-6] + suffix if stem.endswith("_clean") else name
