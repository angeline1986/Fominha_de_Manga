"""Read-only Balanceamento projection for Central V2."""
from pathlib import Path

from .balanceamento import (
    BALANCE_RATIO, _chapter_analysis, _latest_proposal, _merge_root, _natural_key,
)


def read_balance_state(manga: Path) -> dict:
    root = _merge_root(manga)
    directories = sorted(
        (path for path in root.iterdir() if path.is_dir() and not path.name.startswith(".")),
        key=lambda path: _natural_key(path.name),
    ) if root.is_dir() else []
    chapters = []
    for directory in directories:
        result = _chapter_analysis(directory)
        result["proposal"] = _latest_proposal(manga, directory.name)
        chapters.append(result)
    return _state_payload(chapters)


def _state_payload(chapters: list[dict]) -> dict:
    return {
        "ok": True,
        "rule": {
            "threshold_ratio": BALANCE_RATIO,
            "description": "Merge interno menor que 50% da média dos dois vizinhos.",
        },
        "summary": {
            "chapters": len(chapters),
            "balanced": sum(row["status"] == "BALANCEADO" for row in chapters),
            "unbalanced": sum(row["status"] == "DESBALANCEADO" for row in chapters),
        },
        "chapters": chapters,
    }
