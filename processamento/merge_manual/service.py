from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Iterable

from .review_state import build_pending_blocks, natural_key, state_from_review_row
from .selected_ranges import active_selected_ranges, remaining_intervals


def _review_manifest_path(manga: Path, chapter: str) -> Path:
    return (
        manga
        / "FLUXO_SECUNDARIO"
        / "01_MERGE_PROCESSAMENTO"
        / "MERGE_REVIEW"
        / str(chapter)
        / "merge-review.json"
    )


def build_read_state(
    manga: Path,
    chapter_dirs: Iterable[Path],
    *,
    review_state_loader: Callable[[Path], dict[str, Any]],
) -> dict[str, Any]:
    """Monta a fila somente leitura do Merge Manual a partir da Revisão Merge.

    A autoridade de elegibilidade é o mesmo `row_state()` que alimenta a Central.
    O Merge Manual não reexecuta nem reinterpreta a cadeia Auto-Merge I-V.
    """
    chapters: list[dict[str, Any]] = []

    for chapter_dir in sorted(list(chapter_dirs), key=natural_key):
        review_row = review_state_loader(chapter_dir)
        current = state_from_review_row(review_row)
        if not current["eligible"]:
            continue

        row: dict[str, Any] = {
            "chapter": chapter_dir.name,
            "status": current["status"],
            "authoritative_source": current["source"],
            "error": current["error"],
            "manual_range_applied": current.get("manual_range_applied", False),
            "manual_range_confirmed": False,
            "applied_range": current.get("applied_range"),
            "applied_ranges": current.get("applied_ranges", []),
            "review_proposal_exists": _review_manifest_path(manga, chapter_dir.name).is_file(),
            "pending_blocks": [],
            "pending_pages": 0,
            "blocks_count": 0,
        }

        if current["status"] == "pending":
            try:
                selected = active_selected_ranges(manga, chapter_dir.name)
                row["manual_range_confirmed"] = bool(selected)
                row["confirmed_ranges"] = selected
                pending = [(int(item["global_start"]), int(item["global_end"]))
                           for item in current["pending_segments"]]
                chosen = [(item["global_start"], item["global_end"]) for item in selected]
                remaining = remaining_intervals(pending, chosen)
                if not remaining:
                    raise ValueError("Todas as faixas foram confirmadas, mas a composição oficial ainda não foi publicada.")
                blocks = build_pending_blocks(chapter_dir, [
                    {"global_start": start, "global_end": end} for start, end in remaining
                ])
                row["pending_blocks"] = blocks
                row["blocks_count"] = len(blocks)
                row["pending_pages"] = len(
                    {page["file"] for block in blocks for page in block.get("pages") or []}
                )
            except Exception as exc:
                row["status"] = "blocked"
                row["error"] = str(exc)
                row["pending_blocks"] = []
                row["pending_pages"] = 0
                row["blocks_count"] = 0

        chapters.append(row)

    return {
        "ok": True,
        "schema_version": 2,
        "mode": "read_only",
        "source_of_truth": "review_row_state",
        "chapters": chapters,
        "summary": {
            "total": len(chapters),
            "pending": sum(1 for item in chapters if item["status"] == "pending"),
            "resolved": sum(1 for item in chapters if item["status"] == "resolved"),
            "blocked": sum(1 for item in chapters if item["status"] == "blocked"),
        },
    }
