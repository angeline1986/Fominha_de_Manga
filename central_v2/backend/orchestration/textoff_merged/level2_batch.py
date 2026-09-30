"""Batch orchestration for the TextOff Merged Level II runner."""
from __future__ import annotations

import json
from pathlib import Path

from .level2_process import process
from .level2_vision import _atomic_json

def process_batch(jobs: list[dict], progress_path: Path | None = None) -> list[dict]:
    """Process selected chapters with one detector and one inpainter initialization."""
    runtime: dict = {}
    results = []
    total = len(jobs)
    for index, job in enumerate(jobs, 1):
        chapter_progress = Path(str(progress_path) + f".{index}.json") if progress_path else None
        report = process(Path(job["source_dir"]), Path(job["level1_dir"]),
                         Path(job["output_dir"]), Path(job["report"]),
                         chapter_progress, runtime,
                         candidate_pages=set(job.get("candidate_pages", [])))
        results.append({"chapter": job["chapter"], "report": report})
        if progress_path:
            detail = f"Cap. {job['chapter']}: capítulo concluído ({index}/{total})"
            _atomic_json(progress_path, {"percent": round(index * 100 / total), "detail": detail,
                                         "completed": index, "total": total})
    return results
