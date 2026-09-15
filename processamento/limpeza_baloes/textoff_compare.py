"""Consulta de resultados do Texto Off para comparação visual.

Somente leitura: não executa Cleaner V2 e não altera artefatos oficiais.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import json

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


def _manifest_rows(manga: Path, folder_stage: str, manifest_stage: str) -> list[dict]:
    folder_stage = str(folder_stage).upper()
    manifest_stage = str(manifest_stage).upper()
    root = manga / "FLUXO_SECUNDARIO" / "04_TEXTO_OFF" / folder_stage
    if not root.is_dir():
        return []

    rows = []
    for chapter_dir in sorted((p for p in root.iterdir() if p.is_dir()), key=lambda p: p.name):
        manifest_path = chapter_dir / "clean-manifest.json"
        if not manifest_path.is_file():
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            continue

        if manifest.get("algorithm") != "cleaner_v2_panel_cleaner_2_11_11":
            continue
        if not bool(manifest.get("integrity_ok")):
            continue
        if str(manifest.get("source_stage") or "").upper() != manifest_stage:
            continue

        sources = [str(x) for x in (manifest.get("source_artifacts") or [])]
        cleans = [str(x) for x in (manifest.get("clean_artifacts") or [])]
        if not sources or len(sources) != len(cleans):
            continue

        from processamento.limpeza_baloes.textoff_level3 import pending_for_chapter
        level3_pending = pending_for_chapter(manga, chapter_dir.name)

        items = []
        for source_name, clean_name in zip(sources, cleans):
            if Path(source_name).suffix.lower() not in IMAGE_EXTS:
                continue
            if Path(clean_name).suffix.lower() not in IMAGE_EXTS:
                continue
            if not (chapter_dir / clean_name).is_file():
                continue
            pending = level3_pending.get(f"{manifest_stage}:{source_name}")
            items.append({
                "source_file": source_name,
                "clean_file": clean_name,
                "level3_status": pending.get("status") if pending else None,
            })

        if not items:
            continue

        try:
            processed_at = datetime.fromtimestamp(manifest_path.stat().st_mtime).isoformat(timespec="seconds")
        except OSError:
            processed_at = ""

        rows.append({
            "key": f"{manifest_stage}:{chapter_dir.name}",
            "chapter": chapter_dir.name,
            "source": "Original" if manifest_stage == "ORIGINAL" else "Merged",
            "source_stage": manifest_stage,
            "pages": len(items),
            "processed_at": processed_at,
            "status": "Concluído",
            "items": items,
        })
    return rows


def comparison_state(manga: Path) -> dict:
    rows = (
        _manifest_rows(manga, "ORIGINAL", "ORIGINAL")
        + _manifest_rows(manga, "MERGED", "MERGE")
    )

    def chapter_key(row: dict):
        raw = str(row.get("chapter") or "")
        try:
            return (0, float(raw), raw, str(row.get("source_stage") or ""))
        except ValueError:
            return (1, 0.0, raw.lower(), str(row.get("source_stage") or ""))

    rows.sort(key=chapter_key)
    return {
        "schema_version": 1,
        "engine": "Cleaner V2",
        "algorithm": "cleaner_v2_panel_cleaner_2_11_11",
        "rows": rows,
    }


def media_base(manga: Path, chapter: str, kind: str, source_stage: str) -> Path:
    stage = str(source_stage or "").upper()
    if stage == "MERGED":
        stage = "MERGE"
    if stage not in {"ORIGINAL", "MERGE"}:
        raise ValueError("Fonte do Texto Off inválida.")

    chapter = str(chapter or "")
    if not chapter:
        raise ValueError("Capítulo não informado.")

    if kind == "textoff_clean":
        folder_stage = "ORIGINAL" if stage == "ORIGINAL" else "MERGED"
        base = manga / "FLUXO_SECUNDARIO" / "04_TEXTO_OFF" / folder_stage / chapter
    elif kind == "textoff_source":
        base = (
            manga / "IMG" / chapter
            if stage == "ORIGINAL"
            else manga / "FLUXO_SECUNDARIO" / "02_MERGE" / chapter
        )
    else:
        raise ValueError("Tipo de mídia do Texto Off inválido.")

    return base.resolve()
