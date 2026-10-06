"""Derive special-treatment work from persisted Check approvals."""
from __future__ import annotations

import json
from pathlib import Path

from central_v2.backend.orchestration.textoff_special.artifacts import sha256

from .auto_cleaner_check_manifest import (
    _read_check_manifest, _validate_chapter, _write_atomic,
    manifest_path as check_manifest_path,
)
from .stages import stage_chapter

SCHEMA = "textoff_special_treatments_manifest_v1"
MANIFEST_NAME = "special-treatments-manifest.json"
STAGE = "SPECIAL_TREATMENTS"
STATUSES = frozenset({"pending", "processed", "no_change", "failed"})
TREATMENTS = ("degrade", "estilizado", "gradiente_suave")


def manifest_path(manga: Path, chapter: str) -> Path:
    _validate_chapter(chapter)
    root = Path(manga).resolve()
    folder = stage_chapter(root, STAGE, chapter, read_legacy=False).resolve()
    if not folder.is_relative_to(root):
        raise ValueError("Destino de tratamentos especiais fora da obra.")
    return folder / MANIFEST_NAME


def _destination(row: dict) -> tuple[str | None, str | None]:
    # The saved Check type is the decision; source classifications are evidence.
    kind = row.get("tipo")
    if kind == "residuo_degrade":
        return "degrade", None
    if kind == "residuo_gradiente":
        return "gradiente_suave", None
    return None, None


def _occurrence(row: dict, treatment: str | None, reason: str | None) -> dict:
    result = {
        "id": row["id"], "page": row["page"], "tipo": row["tipo"],
        "treatment": treatment, "status": "pending",
        "check_decision": {"id": row["id"], "page": row["page"]},
    }
    for name in (
        "box_normalized", "box_pixels", "origin", "origins",
        "source_references", "source_classification", "source_classifications",
        "candidate", "observacao",
    ):
        if name in row:
            result[name] = row[name]
    if reason:
        result["classification_block"] = reason
    return result


def _build(manga: Path, document: dict, chapter: str,
           source_hash: str, check: dict) -> dict:
    buckets = {name: [] for name in TREATMENTS}
    unclassified = []
    seen: dict[tuple[str, str], dict] = {}
    rows = sorted(check["approved_occurrences"],
                  key=lambda row: (str(row.get("page", "")), str(row.get("id", ""))))
    for row in rows:
        treatment, reason = _destination(row)
        if treatment is None and reason is None:
            continue
        if not isinstance(row.get("id"), str) or not isinstance(row.get("page"), str):
            raise ValueError("Ocorrência aprovada do Check sem id ou página.")
        key = (row["page"], row["id"])
        if key in seen:
            if seen[key] != row:
                raise ValueError("Identidade duplicada com decisões divergentes no Check.")
            continue
        seen[key] = row
        if not isinstance(row.get("box_normalized"), dict):
            reason = "roi_normalizada_ausente"
            treatment = None
        item = _occurrence(row, treatment, reason)
        if treatment is None:
            unclassified.append(item)
        else:
            buckets[treatment].append(item)
    return {
        "schema": SCHEMA, "version": 1,
        "provider": document["provider"], "manga": document["obra"],
        "chapter": chapter,
        "source_check": {
            "path": str(check_manifest_path(manga, chapter).relative_to(manga)),
            "sha256": source_hash, "schema": check["schema"],
            "version": check["version"], "updated_at": check.get("updated_at"),
        },
        "treatments": buckets, "unclassified": unclassified,
    }


def rebuild_special_treatments(manga: Path, document: dict,
                               chapter: str) -> tuple[Path, dict, bool]:
    """Refresh changed routing; identical projections retain processing status."""
    manga = Path(manga).resolve()
    check_path = check_manifest_path(manga, chapter)
    before_hash = sha256(check_path)
    check = _read_check_manifest(check_path, document)
    payload = _build(manga, document, chapter, before_hash, check)
    if sha256(check_path) != before_hash:
        raise ValueError("O Check mudou durante o bootstrap.")
    target = manifest_path(manga, chapter)
    if target.is_file():
        existing = json.loads(target.read_text(encoding="utf-8"))
        if (isinstance(existing, dict) and existing.get("schema") == SCHEMA
                and existing.get("source_check") == payload["source_check"]):
            current = json.loads(json.dumps(existing))
            for rows in [*current.get("treatments", {}).values(),
                         current.get("unclassified", [])]:
                if isinstance(rows, list):
                    for row in rows:
                        if isinstance(row, dict):
                            row["status"] = "pending"
            if current == payload:
                return target, existing, False
    _write_atomic(target, payload)
    return target, payload, True
