import json
from pathlib import Path

from .artifacts import (
    execution_dir, merge_dir, replace_execution_artifacts, report_path, validate_report,
)
from .runtime import run, validate_profile_id


def execute(
    manga: Path,
    chapters: list[str],
    progress,
    profile_id: str,
    preflight=None,
) -> list[dict]:
    profile_id = validate_profile_id(profile_id)
    results = []
    total = len(chapters)

    for index, chapter in enumerate(chapters, 1):
        if preflight:
            preflight()

        source = merge_dir(manga, chapter)
        output_dir = execution_dir(manga, chapter)
        path = report_path(manga, chapter)
        with replace_execution_artifacts(output_dir):
            run(source, output_dir, profile_id)
            try:
                report = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise RuntimeError(
                    f"Não foi possível carregar o report do capítulo {chapter}."
                ) from exc
            report = validate_report(report, profile_id)
        counts = report["checkpoints"]["result"]
        results.append({
            "chapter": chapter,
            "profile_id": profile_id,
            "pages": counts["pages"],
            "balloons": counts["crops"],
            "coverage_ge_075": counts["coverageGe075"],
            "candidates": counts["candidates"],
        })

        progress(chapter, {
            "completed": index,
            "total": total,
            "value": index,
            "max": total,
            "percent": int(index * 100 / total) if total else 100,
            "stage": "bubble_sommelier",
            "message": f"Curadoria {chapter} concluída",
        })

    return results
