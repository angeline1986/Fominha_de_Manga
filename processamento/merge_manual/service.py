from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Iterable

from .review_state import build_pending_blocks, natural_key, state_from_review_row


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
            "review_proposal_exists": _review_manifest_path(manga, chapter_dir.name).is_file(),
            "pending_blocks": [],
            "pending_pages": 0,
            "blocks_count": 0,
        }

        if current["status"] == "pending":
            try:
                blocks = build_pending_blocks(chapter_dir, current["pending_segments"])
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
