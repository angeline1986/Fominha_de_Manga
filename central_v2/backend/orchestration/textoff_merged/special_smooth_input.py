"""Resolve Check-approved Suave ROIs and their current Consolidado image."""
from __future__ import annotations

import json
from pathlib import Path

from central_v2.backend.orchestration.textoff_special.artifacts import sha256
from central_v2.backend.orchestration.textoff_special.inputs import validate_selections

from .auto_cleaner_check_manifest import (
    _read_check_manifest, manifest_path as check_manifest_path,
)
from .special_degrade_input import selected_input
from .special_treatments_manifest import SCHEMA, manifest_path as special_manifest_path


def pending_pages(manga: Path, provider: str, chapter: str,
                  *, retry: bool = False) -> tuple[Path, str, dict, dict]:
    manga = Path(manga).resolve()
    path = special_manifest_path(manga, chapter)
    digest = sha256(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if (payload.get("schema") != SCHEMA or payload.get("version") != 1
            or payload.get("provider") != provider or payload.get("manga") != manga.name
            or payload.get("chapter") != chapter):
        raise ValueError("Manifesto Especial incompatível com a obra selecionada.")
    check_path = check_manifest_path(manga, chapter)
    if (payload.get("source_check", {}).get("path") != str(check_path.relative_to(manga))
            or payload["source_check"].get("sha256") != sha256(check_path)):
        raise ValueError("Manifesto Especial obsoleto em relação ao Check.")
    approved = _read_check_manifest(check_path, {
        "provider": provider, "obra": manga.name, "capitulo": chapter,
    })["approved_occurrences"]
    decisions = {(row.get("page"), row.get("id")): row for row in approved}
    rows = (payload.get("treatments") or {}).get("gradiente_suave")
    if not isinstance(rows, list):
        raise ValueError("Tratamento Suave ausente do Manifesto Especial.")
    groups, seen = {}, set()
    for row in rows:
        if (not isinstance(row, dict) or row.get("treatment") != "gradiente_suave"
                or row.get("tipo") != "residuo_gradiente"):
            raise ValueError("Ocorrência incompatível com Gradiente Suave.")
        decision = decisions.get((row.get("page"), row.get("id")))
        if (decision is None or decision.get("tipo") != row.get("tipo")
                or decision.get("box_pixels") != row.get("box_pixels")):
            raise ValueError("Ocorrência Suave não corresponde à decisão aprovada do Check.")
        eligible = row.get("status") == ("failed" if retry else "pending")
        if not eligible:
            continue
        page, identity = row.get("page"), row.get("id")
        if (not isinstance(page, str) or not page or Path(page).name != page
                or not isinstance(identity, str) or not identity or (page, identity) in seen):
            raise ValueError("Página ou identidade inválida no Manifesto Especial.")
        seen.add((page, identity))
        validate_selections([row.get("box_pixels")])
        groups.setdefault(page, []).append(row)
    if sha256(path) != digest:
        raise ValueError("Manifesto Especial mudou durante a leitura.")
    if not groups:
        raise ValueError(f"Capítulo {chapter} não possui Suave elegível.")
    return path, digest, payload, groups


def validate_chapters(manga: Path, provider: str, chapters: object,
                      *, retry: bool = False) -> list[str]:
    if (not isinstance(chapters, list) or not chapters
            or any(not isinstance(name, str) or not name or Path(name).name != name
                   or name in {".", ".."} or "\\" in name for name in chapters)
            or len(set(chapters)) != len(chapters)):
        raise ValueError("Selecione capítulos válidos sem repetição.")
    for chapter in chapters:
        pending_pages(manga, provider, chapter, retry=retry)
    return chapters


__all__ = ["pending_pages", "selected_input", "validate_chapters"]
