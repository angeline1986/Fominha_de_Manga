"""Build an in-memory Artístico reexecution plan from the current Check."""
from datetime import datetime, timezone
import json
from pathlib import Path
from uuid import uuid4

from central_v2.backend.orchestration.textoff_special.artifacts import sha256

from .auto_cleaner_check_manifest import (
    _read_check_manifest, manifest_path as check_manifest_path,
)
from .special_treatments_manifest import _build, _decision_fields, _preserve_runtime_state, manifest_path


def build_plan(manga: Path, provider: str, chapter: str,
               selected: list[dict]) -> dict:
    manga = Path(manga).resolve()
    special = manifest_path(manga, chapter)
    previous_bytes = special.read_bytes()
    previous = json.loads(previous_bytes.decode("utf-8"))
    old_rows = (previous.get("treatments") or {}).get("estilizado")
    if not isinstance(old_rows, list) or not any(
            isinstance(row, dict) and row.get("status") in {"processed", "no_change"}
            for row in old_rows):
        raise ValueError("Não há resultado Artístico anterior para reexecutar.")
    if (not isinstance(selected, list) or not selected
            or any(not isinstance(item, dict) or set(item) - {"page", "id", "expected_sha256"}
                   or not isinstance(item.get("page"), str)
                   or not isinstance(item.get("id"), str) for item in selected)):
        raise ValueError("Selecione ocorrências Artístico válidas.")
    keys = [(item["page"], item["id"]) for item in selected]
    if len(set(keys)) != len(keys):
        raise ValueError("Ocorrência Artístico selecionada mais de uma vez.")
    old = {(row.get("page"), row.get("id")): row for row in old_rows
           if isinstance(row, dict)}
    if any(key not in old or old[key].get("status") not in {"processed", "no_change"}
           for key in keys):
        raise ValueError("Ocorrência Artístico selecionada não possui resultado anterior.")
    check = check_manifest_path(manga, chapter)
    check_hash = sha256(check)
    document = {"provider": provider, "obra": manga.name, "capitulo": chapter}
    decisions = _read_check_manifest(check, document)
    fresh = _build(manga, document, chapter, check_hash, decisions)
    if sha256(check) != check_hash:
        raise ValueError("Check mudou durante a preparação Artístico.")
    _preserve_runtime_state(fresh, previous)
    for treatment, rows in (previous.get("treatments") or {}).items():
        old_by_key = {(row.get("page"), row.get("id")): row for row in rows}
        new_by_key = {(row.get("page"), row.get("id")): row
                      for row in fresh["treatments"].get(treatment, [])}
        if set(old_by_key) != set(new_by_key) or any(
                new_by_key[key] != row for key, row in old_by_key.items()
                if treatment != "estilizado" or key not in keys):
            raise ValueError("Check alterou outra ocorrência; reexecução individual bloqueada.")
    fresh_rows = {(row["page"], row["id"]): row
                  for row in fresh["treatments"]["estilizado"]}
    if any(key not in fresh_rows or _decision_fields(fresh_rows[key]) != _decision_fields(old[key])
           for key in keys):
        raise ValueError("ROI aprovada da ocorrência Artístico mudou; revisão necessária.")
    fresh["reexecution_history"] = list(previous.get("reexecution_history", []))
    run_id = uuid4().hex
    fresh["reexecution_history"].append({
        "id": run_id, "treatment": "estilizado",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "previous_check_sha256": (previous.get("source_check") or {}).get("sha256"),
        "current_check_sha256": check_hash,
        "superseded_occurrences": [
            {field: old[key][field] for field in ("id", "page", "status", "box_pixels", "result")
             if field in old[key]} for key in keys],
    })
    for row in fresh["treatments"]["estilizado"]:
        if (row["page"], row["id"]) not in keys:
            continue
        row["status"] = "pending"
        row.pop("result", None)
        row.pop("error", None)
    return {"id": run_id, "special_path": special, "special_hash": sha256(special),
            "previous_special_bytes": previous_bytes, "payload": fresh,
            "check_path": check, "check_hash": check_hash}
