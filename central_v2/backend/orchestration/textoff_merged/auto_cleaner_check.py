"""Read existing TextOff suggestions and persist Auto-Cleaner Check decisions."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

from .residue_occurrences import TYPE_LABELS
from .auto_cleaner_check_geometry import _to_contract_occurrence
from .auto_cleaner_check_manifest import (
    CHECK_STAGE, MANIFEST_NAME, SCHEMA, _read_check_manifest, _validate_chapter,
    _write_atomic, manifest_path,
)
from .auto_cleaner_check_sources import (
    SOURCE_NAMES, _initial_occurrences, _stale_sources, _with_source_health,
    source_snapshot,
)


class StaleCheckSourcesError(ValueError):
    """The persisted sources changed while an initial Check draft was open."""


def load_check_page(manga: Path, document: dict, chapter: str, page: str,
                    pairs: list[dict]) -> dict:
    """Return saved Check decisions or first-open suggestions for one page."""
    from .auto_cleaner_check_manifest import _validate_page
    _validate_page(page, pairs)
    path = manifest_path(manga, chapter)
    current_sources = source_snapshot(manga, document, chapter)
    seeded, source_health = _initial_occurrences(
        manga, document, chapter, pairs, current_sources,
    )
    source_status = _with_source_health(current_sources, source_health)
    if path.is_file():
        payload = _read_check_manifest(path, document)
        approved = payload["approved_occurrences"]
        occurrences = [dict(item) for item in approved if item.get("page") == page]
        stale = _stale_sources(payload.get("source_snapshot", {}), current_sources)
        return {
            "page": page, "occurrences": occurrences,
            "cataloged": bool(occurrences), "decision_persisted": True,
            "source_snapshot": payload.get("source_snapshot", {}),
            "source_status": source_status, "stale_sources": stale,
        }
    occurrences = [item for item in seeded if item["page"] == page]
    pair = next(item for item in pairs if item["name"] == page)
    with Image.open(pair["after"]) as image:
        width, height = image.size
    occurrences = [_to_contract_occurrence(item, index + 1, page, width, height)
                   for index, item in enumerate(occurrences)]
    return {
        "page": page, "occurrences": occurrences,
        "cataloged": bool(occurrences), "decision_persisted": False,
        "source_snapshot": current_sources, "source_status": source_status,
        "stale_sources": [],
    }


def check_occurrence_counts(manga: Path, document: dict, chapter: str,
                            pairs: list[dict]) -> dict[str, int]:
    """Return counts for the comparison page list without changing any files."""
    path = manifest_path(manga, chapter)
    if path.is_file():
        payload = _read_check_manifest(path, document)
        counts = {}
        for item in payload["approved_occurrences"]:
            page = item.get("page")
            if isinstance(page, str):
                counts[page] = counts.get(page, 0) + 1
        return counts
    snapshot = source_snapshot(manga, document, chapter)
    seeded, _ = _initial_occurrences(manga, document, chapter, pairs, snapshot)
    counts = {}
    for item in seeded:
        page = item["page"]
        counts[page] = counts.get(page, 0) + 1
    return counts


def save_check_decision(manga: Path, document: dict, chapter: str,
                        pages: list[tuple[str, list[dict]]],
                        pairs: list[dict], source_snapshot_value: object) -> dict:
    """Persist page edits while retaining the chapter-wide initial suggestions."""
    from .auto_cleaner_check_manifest import _validate_page
    if not pages:
        raise ValueError("O lote do Check não contém páginas.")
    for page, _ in pages:
        _validate_page(page, pairs)
    if not isinstance(source_snapshot_value, dict):
        raise ValueError("Referências de origem do Check inválidas.")
    path = manifest_path(manga, chapter)
    if path.is_file():
        existing = _read_check_manifest(path, document)
        approved = [dict(item) for item in existing["approved_occurrences"]]
        saved_snapshot = existing.get("source_snapshot", {})
    else:
        current_snapshot = source_snapshot(manga, document, chapter)
        if source_snapshot_value != current_snapshot:
            raise StaleCheckSourcesError(
                "As fontes mudaram enquanto o Check estava aberto. Recarregue o capítulo antes de salvar."
            )
        approved, _ = _initial_occurrences(manga, document, chapter, pairs, current_snapshot)
        saved_snapshot = current_snapshot
    replacements = {page: [dict(row, page=page) for row in rows] for page, rows in pages}
    updated = [item for item in approved if item.get("page") not in replacements]
    for page in sorted(replacements):
        updated.extend(replacements[page])
    updated.sort(key=lambda item: (str(item.get("page", "")), str(item.get("id", ""))))
    payload = {
        "schema": SCHEMA, "version": 1, "provider": document["provider"],
        "manga": document["obra"], "chapter": chapter,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "source_snapshot": saved_snapshot, "approved_occurrences": updated,
    }
    _write_atomic(path, payload)
    return payload
