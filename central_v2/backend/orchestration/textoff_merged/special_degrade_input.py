"""Resolve approved Degradê ROIs and their current Consolidado image."""
from __future__ import annotations

import json
from pathlib import Path

from central_v2.backend.orchestration.textoff_special.artifacts import sha256
from central_v2.backend.orchestration.textoff_special.inputs import validate_selections

from .auto_cleaner_check_manifest import (
    _read_check_manifest, manifest_path as check_manifest_path,
)
from .final_consolidated import final_manifest_path, read_final_page
from .final_consolidated_validation import require_official_paint_source
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
    check = payload.get("source_check") or {}
    check_path = check_manifest_path(manga, chapter)
    if (check.get("path") != str(check_path.relative_to(manga))
            or check.get("sha256") != sha256(check_path)):
        raise ValueError("Manifesto Especial obsoleto em relação ao Check.")
    approved = _read_check_manifest(check_path, {
        "provider": provider, "obra": manga.name, "capitulo": chapter,
    })["approved_occurrences"]
    decisions = {(row.get("page"), row.get("id")): row for row in approved}
    rows = (payload.get("treatments") or {}).get("degrade")
    if not isinstance(rows, list):
        raise ValueError("Tratamento Degradê ausente do Manifesto Especial.")
    groups: dict[str, list[dict]] = {}
    ids = set()
    for row in rows:
        if (not isinstance(row, dict) or row.get("treatment") != "degrade"
                or row.get("tipo") != "residuo_degrade"):
            raise ValueError("Ocorrência incompatível com Degradê.")
        decision = decisions.get((row.get("page"), row.get("id")))
        if (decision is None or decision.get("tipo") != row.get("tipo")
                or decision.get("box_pixels") != row.get("box_pixels")):
            raise ValueError("Ocorrência Degradê não corresponde à decisão aprovada do Check.")
        if row.get("status") not in ({"pending", "failed"} if retry else {"pending"}):
            continue
        page, identity = row.get("page"), row.get("id")
        if (not isinstance(page, str) or not page or Path(page).name != page
                or not isinstance(identity, str) or not identity or (page, identity) in ids):
            raise ValueError("Página ou identidade inválida no Manifesto Especial.")
        ids.add((page, identity))
        validate_selections([row.get("box_pixels")])
        groups.setdefault(page, []).append(row)
    if sha256(path) != digest:
        raise ValueError("Manifesto Especial mudou durante a leitura.")
    if not groups:
        raise ValueError(f"Capítulo {chapter} não possui Degradê pendente.")
    return path, digest, payload, groups


def selected_input(manga: Path, chapter: str, page: str) -> dict:
    manga = Path(manga).resolve()
    record, image, digest = read_final_page(manga, chapter, page)
    require_official_paint_source(record)
    manifest = final_manifest_path(manga, chapter).resolve()
    return {"page": page, "selected_from": record["origin"], "path": str(image),
            "filename": page, "sha256": record["sha256"], "level": "CONSOLIDADO_FINAL",
            "consolidated_manifest": str(manifest), "consolidated_manifest_sha256": digest}
