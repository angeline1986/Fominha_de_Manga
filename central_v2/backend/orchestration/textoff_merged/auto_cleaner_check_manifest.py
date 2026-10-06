"""Manifest contract, safe paths, validation, and atomic persistence."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile

from .stages import stage_chapter

SCHEMA = "textoff_auto_cleaner_check_manifest_v1"
MANIFEST_NAME = "auto-cleaner-check-manifest.json"
CHECK_STAGE = "04_AUTO_CLEANER_CHECK"


def _validate_chapter(chapter: str) -> None:
    if (not isinstance(chapter, str) or not chapter or chapter in {".", ".."}
            or Path(chapter).name != chapter or "\\" in chapter):
        raise ValueError("Capítulo inválido.")


def manifest_path(manga: Path, chapter: str) -> Path:
    _validate_chapter(chapter)
    root = Path(manga).resolve()
    folder = stage_chapter(Path(manga), CHECK_STAGE, chapter, read_legacy=False).resolve()
    if not folder.is_relative_to(root):
        raise ValueError("Destino do Check fora do diretório autorizado da obra.")
    target = folder / MANIFEST_NAME
    if not target.resolve().is_relative_to(folder):
        raise ValueError("Manifesto do Check fora do estágio autorizado.")
    return target


def _validate_page(page: str, pairs: list[dict]) -> None:
    if (not isinstance(page, str) or not page or page in {".", ".."}
            or Path(page).name != page or "\\" in page
            or not any(pair.get("name") == page for pair in pairs)):
        raise ValueError("Página não pertence à comparação autorizada do Check.")


def _read_check_manifest(path: Path, document: dict) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if (not isinstance(payload, dict) or payload.get("schema") != SCHEMA
            or payload.get("version") != 1
            or payload.get("provider") != document["provider"]
            or payload.get("manga") != document["obra"]
            or payload.get("chapter") != document["capitulo"]
            or not isinstance(payload.get("source_snapshot"), dict)
            or not isinstance(payload.get("approved_occurrences"), list)
            or not all(isinstance(row, dict) for row in payload["approved_occurrences"])):
        raise ValueError("O manifesto do Auto-Cleaner Check tem estrutura incompatível.")
    return payload


def _write_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
