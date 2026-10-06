import json
from pathlib import Path

from .artifacts import images, merge_dir, validate_report
from central_v2.backend.orchestration.textoff_merged.stages import stage_chapter
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
    root = manga / "FLUXO_SECUNDARIO" / "02_MERGE"
    chapters = []
    if root.is_dir():
        chapter_names = sorted(
            (path.name for path in root.iterdir() if path.is_dir()),
            key=_sort,
        )
        for chapter in chapter_names:
            imgs = images(merge_dir(manga, chapter))
            state = _sommelier_state(stage_chapter(manga, "BUBBLE_SOMMELIER", chapter) / "report.json")
            observe_shadow_read(manga, "bubble_sommelier", chapter)
            chapters.append({
                "chapter": chapter,
                "merge_count": len(imgs),
                "merge_valid": bool(imgs),
                "sommelier": state,
            })
    return {"chapters": chapters}
