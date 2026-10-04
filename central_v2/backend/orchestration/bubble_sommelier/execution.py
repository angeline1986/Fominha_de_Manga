import json
from pathlib import Path
import time

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
    *,
    provider: str | None = None,
    manga_name: str | None = None,
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
        runtime_started = time.monotonic()
        page_started = {}

        def report_runtime_progress(event: dict) -> None:
            event_type = event.get("type")
            if event_type == "run_started":
                total_pages = int(event.get("total_pages") or 0)
                message = "Execução do capítulo iniciada"
                progress(chapter, {
                    "stage": "run_started", "percent": 0, "completed": 0,
                    "total": total_pages, "message": message,
                    "provider": provider or manga.parent.name,
                    "manga": manga_name or manga.name, "profile_id": profile_id,
                })
            elif event_type == "page_started":
                current, total = int(event["current"]), int(event["total"])
                page_started[current] = time.perf_counter()
                progress(chapter, {
                    "stage": "page_started", "page_index": current,
                    "percent": int((current - 1) * 100 / total) if total else 0,
                    "completed": current - 1, "total": total,
                    "message": f"{event['page_id']} · inferência em andamento",
                })
            elif event_type == "page_completed":
                current, total = int(event["current"]), int(event["total"])
                percent = int(event["percent"])
                duration = (time.perf_counter() - page_started.pop(current)
                            if current in page_started else None)
                progress(chapter, {
                    "stage": "page", "page_index": current,
                    "percent": percent, "completed": current, "total": total,
                    "duration": duration,
                    "bubbles": event.get("bubbles"),
                    "candidates": event.get("candidates"),
                    "message": f"{event['page_id']} · página concluída",
                })

        with replace_execution_artifacts(output_dir):
            run(
                source,
                output_dir,
                profile_id,
                on_progress=report_runtime_progress,
                progress_context={
                    "provider": provider or manga.parent.name,
                    "manga": manga_name or manga.name,
                    "chapter": chapter,
                },
            )
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

        elapsed = time.monotonic() - runtime_started
        progress(chapter, {
            "completed": index,
            "total": total,
            "value": index,
            "max": total,
            "percent": int(index * 100 / total) if total else 100,
            "stage": "completed",
            "message": "Execução do capítulo concluída",
            "pages": counts["pages"], "bubbles": counts["crops"],
            "candidates": counts["candidates"], "duration": elapsed,
        })

    return results
