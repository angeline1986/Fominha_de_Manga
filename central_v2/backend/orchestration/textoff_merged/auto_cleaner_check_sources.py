"""Snapshot source artifacts and assemble the Check's first-open suggestions."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .residue_occurrences import MANIFEST_NAME as RESIDUE_MANIFEST_NAME
from .stages import LEVEL3, stage_chapter
from central_v2.backend.orchestration.bubble_sommelier.artifacts import report_path as sommelier_report_path
from .auto_cleaner_check_extractors import (
    _manual_occurrences, _mapear_occurrences, _sommelier_occurrences,
)
from .auto_cleaner_check_geometry import _merge_automatic_sources

SOURCE_NAMES = ("mapear", "sommelier", "residue_occurrences")


def source_snapshot(manga: Path, document: dict, chapter: str) -> dict:
    paths = _source_paths(manga, chapter)
    snapshot = {}
    for source in SOURCE_NAMES:
        relative_path, path = paths[source]
        status = "available" if path.is_file() else "missing"
        digest = _sha256(path) if status == "available" else None
        snapshot[source] = {"path": relative_path, "status": status, "sha256": digest}
    return snapshot


def _with_source_health(snapshot: dict, health: dict) -> dict:
    return {name: {**snapshot.get(name, {}), "status": health.get(name, "missing")}
            for name in SOURCE_NAMES}


def _initial_occurrences(manga: Path, document: dict, chapter: str,
                         pairs: list[dict], snapshot: dict) -> tuple[list[dict], dict]:
    pages = {pair["name"]: pair for pair in pairs}
    automatic_sources = {"mapear": [], "sommelier": []}
    statuses = {}
    for loader in (_mapear_occurrences, _sommelier_occurrences):
        name = "mapear" if loader is _mapear_occurrences else "sommelier"
        source_info = snapshot.get(name, {})
        if source_info.get("status") != "available":
            statuses[name] = source_info.get("status", "missing")
            continue
        try:
            rows = loader(manga, chapter, pages)
            statuses[name] = "available"
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            rows = []
            statuses[name] = "invalid"
        automatic_sources[name] = rows
    automatic = _merge_automatic_sources(
        automatic_sources["mapear"], automatic_sources["sommelier"],
    )

    manual_status = snapshot.get("residue_occurrences", {}).get("status", "missing")
    manual_rows = []
    if manual_status == "available":
        try:
            manual_rows = _manual_occurrences(manga, document, chapter, pages)
            statuses["residue_occurrences"] = "available"
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            statuses["residue_occurrences"] = "invalid"
    else:
        statuses["residue_occurrences"] = manual_status
    seen_ids = {item["id"] for item in automatic}
    for item in manual_rows:
        if item["id"] in seen_ids:
            item["id"] = f"manual-{item['id']}"[:128]
        seen_ids.add(item["id"])
    return sorted(automatic + manual_rows,
                  key=lambda item: (item["page"], item["origin"], item["id"])), statuses


def _source_paths(manga: Path, chapter: str) -> dict[str, tuple[str, Path]]:
    mapear = stage_chapter(Path(manga), LEVEL3, chapter) / "json" / "styled-balloon-report.json"
    sommelier = sommelier_report_path(Path(manga), chapter)
    residue = (stage_chapter(Path(manga), "RESIDUE_OCCURRENCES", chapter,
                             read_legacy=False) / RESIDUE_MANIFEST_NAME)
    root = Path(manga).resolve()
    result = {}
    for name, path, relative in (
        ("mapear", mapear, f"TO_MERGED_NIVEL_III/{chapter}/json/styled-balloon-report.json"),
        ("sommelier", sommelier, f"BUBBLE_SOMMELIER/{chapter}/report.json"),
        ("residue_occurrences", residue, f"RESIDUE_OCCURRENCES/{chapter}/{RESIDUE_MANIFEST_NAME}"),
    ):
        if not path.resolve().is_relative_to(root):
            raise ValueError(f"Fonte fora do diretório autorizado: {relative}")
        result[name] = (relative, path)
    return result


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stale_sources(previous: dict, current: dict) -> list[str]:
    return [name for name in SOURCE_NAMES if previous.get(name) != current.get(name)]
