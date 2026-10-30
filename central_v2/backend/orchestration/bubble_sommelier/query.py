import json
from pathlib import Path
from central_v2.backend.state.work_layout import merge_root

from .artifacts import images, merge_dir, validate_report
from central_v2.backend.orchestration.textoff_merged.unexecuted_stage import both_absent
from central_v2.backend.orchestration.textoff_merged.stages import stage_chapter
from central_v2.backend.orchestration.textoff_merged.artifact_migration import ArtifactAuthorityUnavailable
from central_v2.backend.orchestration.textoff_merged.artifact_shadow_read import (
    observe_shadow_read,
)


def _sort(value: str):
    numeric = value.replace(".", "", 1).isdigit()
    return (not numeric, float(value) if numeric else value)


def _sommelier_state(report_path_value: Path) -> dict | None:
    try:
        report = json.loads(report_path_value.read_text(encoding="utf-8"))
        profile_id = report.get("profile_id") if isinstance(report, dict) else None
        report = validate_report(report, profile_id)
    except (OSError, json.JSONDecodeError, ValueError, RuntimeError):
        return None

    result = report["checkpoints"]["result"]
    return {
        "analyzed": True,
        "profile_id": profile_id,
        "balloons": result["crops"],
        "candidates": result["candidates"],
        "coverage_ge_075": result["coverageGe075"],
    }


def query(manga: Path) -> dict:
    root = merge_root(manga)
    chapters = []
    if root.is_dir():
        chapter_names = sorted(
            (path.name for path in root.iterdir() if path.is_dir()),
            key=_sort,
        )
        for chapter in chapter_names:
            imgs = images(merge_dir(manga, chapter))
            if both_absent(manga, "BUBBLE_SOMMELIER", "03_BUBBLE_SOMMELIER", chapter):
                report_dir = None
            else:
                report_dir = stage_chapter(manga, "BUBBLE_SOMMELIER", chapter)
            state = _sommelier_state(report_dir / "report.json") if report_dir else None
            observe_shadow_read(manga, "bubble_sommelier", chapter, debug_only=True)
            chapters.append({
                "chapter": chapter,
                "merge_count": len(imgs),
                "merge_valid": bool(imgs),
                "sommelier": state,
            })
    return {"chapters": chapters}
