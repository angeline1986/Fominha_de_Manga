"""Read-only Mapear projection; chapters validate independently in parallel."""
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
import hashlib
import json
from pathlib import Path

from processamento.unificacao_imagens import image_stitcher as v3
from central_v2.backend.state.sorting import natural_sort_key
from central_v2.backend.state.work_layout import images_root, textoff_root

from .artifact_paths import json_file
from .unexecuted_stage import both_absent
from .artifact_shadow_read import observe_shadow_read
from .artifact_migration import ArtifactAuthorityUnavailable
from .consolidated import consolidated_is_current
from .manifests import _manifest_matches_merge, _stage_manifest
from .stages import CONSOLIDATED, LEVEL1, LEVEL3, stage_chapter
from .styled_balloon_detector import ALGORITHM


def query_level3(manga: Path, merge_rows: dict | None = None) -> dict:
    root = images_root(manga)
    chapters = sorted((path.name for path in root.iterdir() if path.is_dir()),
                      key=natural_sort_key) if root.is_dir() else []
    if merge_rows is None:
        from .query import query_merged
        merge_rows = {row["chapter"]: row for row in query_merged(manga)["chapters"]}
    if len(chapters) < 2:
        rows = [_chapter_row(manga, chapter, merge_rows) for chapter in chapters]
    else:
        with ThreadPoolExecutor(max_workers=min(16, len(chapters))) as pool:
            pending = [pool.submit(copy_context().run, _chapter_row, manga, chapter, merge_rows)
                       for chapter in chapters]
            rows = [task.result() for task in pending]
    return {"chapters": rows, "total": len(rows)}


def _chapter_row(manga: Path, chapter: str, merge_rows: dict) -> dict:
    if all(both_absent(manga, legacy, target, chapter) for legacy, target in (
        ("TO_MERGED_NIVEL_I", "01_AUTO_CLEANER"),
        (CONSOLIDATED, "02_MAPEAR/INPUT_CONSOLIDADO"),
        ("TO_MERGED_NIVEL_III", "02_MAPEAR"),
    )):
        merge = merge_rows.get(chapter, {})
        return {"chapter": chapter, "merge_valid": bool(merge.get("merge_valid")),
                "merge_count": int(merge.get("merge_count") or 0),
                "cleaned": False, "selectable": False,
                "level3_status": "missing_level1", "pages_analyzed": 0,
                "candidate_count": 0, "candidate_pages": []}
    consolidated_ready = consolidated_is_current(manga, chapter)
    ready = consolidated_ready or _manifest_matches_merge(
        _stage_manifest(manga, LEVEL1, chapter), manga, chapter)
    if both_absent(manga, "TO_MERGED_NIVEL_III", "02_MAPEAR", chapter):
        path = textoff_root(manga) / "02_MAPEAR" / chapter / "json/clean-manifest.json"
    else:
        path = stage_chapter(manga, LEVEL3, chapter) / "json/clean-manifest.json"
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        manifest = {}
    observe_shadow_read(manga, "mapear", chapter, debug_only=True)
    current = (ready and consolidated_ready and manifest.get("algorithm") == ALGORITHM
               and manifest.get("source_consolidated_manifest_sha256") ==
               _file_sha256(stage_chapter(manga, CONSOLIDATED, chapter) / "json/clean-manifest.json")
               and manifest.get("integrity_ok") is True
               and manifest.get("source_merge_manifest_sha256") ==
               _file_sha256(v3.merge_manifest_path(images_root(manga) / chapter))
               and bool(json_file(path.parent.parent, "styled-balloon-report.json").is_file()))
    candidate_pages = _candidate_pages(path.parent.parent, manga, chapter) if current else []
    merge = merge_rows.get(chapter, {})
    return {
        "chapter": chapter, "merge_valid": bool(merge.get("merge_valid")),
        "merge_count": int(merge.get("merge_count") or 0),
        "cleaned": current, "selectable": ready and not current,
        "level3_status": "processed" if current else "pending" if ready else "missing_level1",
        "pages_analyzed": int(manifest.get("pages_analyzed") or 0) if current else 0,
        "candidate_count": int(manifest.get("candidate_count") or 0) if current else 0,
        "candidate_pages": candidate_pages,
    }


def _candidate_pages(chapter_dir: Path, manga: Path, chapter: str) -> list[dict]:
    try:
        report = json.loads(json_file(chapter_dir, "styled-balloon-report.json").read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return []
    pages = {}
    for page in report.get("pages", []):
        candidates = page.get("styled_balloon_candidates") if isinstance(page, dict) else None
        if not candidates or not isinstance(page.get("source"), str):
            continue
        pages[page["source"]] = {"source": page["source"], "candidates": [
            {"bbox": item.get("bbox"), "candidate_type": item.get("candidate_type"),
             "segmenter_confidence": item.get("segmenter_confidence"),
             "features": item.get("features", {})}
            for item in candidates if isinstance(item, dict) and _valid_candidate(item)
        ]}
    try:
        from .transparent_check_adapter import load_suggestions
        transparent = load_suggestions(manga, chapter)
    except (OSError, ValueError, TypeError, KeyError):
        transparent = []
    for item in transparent:
        source = Path(item["page"])
        image_name = f"{source.stem}_clean{source.suffix}"
        page = pages.setdefault(image_name, {"source": image_name, "candidates": []})
        page["candidates"].append({
            "box": item["box"], "candidate_type": "transparent_balloon",
            "balloon": item["source_references"][0]["balloon"],
        })
    return [page for page in pages.values() if page["candidates"]]


def _valid_candidate(item: dict) -> bool:
    bbox = item.get("bbox")
    return (isinstance(bbox, list) and len(bbox) == 4
            and all(isinstance(value, (int, float)) for value in bbox)
            and isinstance(item.get("candidate_type"), str))


def _file_sha256(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None
