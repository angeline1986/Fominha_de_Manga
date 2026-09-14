"""Estado do Texto Off — Nível III (correção assistida).

Este módulo, neste primeiro incremento, apenas registra páginas sinalizadas para
correção. Não executa LaMa, não altera imagens e não promove artefatos oficiais.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import os
import tempfile

SCHEMA_VERSION = 1
STATUS_PENDING = "PENDENTE_NIVEL3"
VALID_STAGES = {"ORIGINAL", "MERGE"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


def _root(manga: Path) -> Path:
    return manga / "FLUXO_SECUNDARIO" / "04_TEXTO_OFF" / "NIVEL3"


def _chapter_dir(manga: Path, chapter: str) -> Path:
    chapter = str(chapter or "").strip()
    if not chapter or chapter in {".", ".."} or "/" in chapter or "\\" in chapter:
        raise ValueError("Capítulo inválido para o Nível III.")
    return _root(manga) / chapter


def _state_path(manga: Path, chapter: str) -> Path:
    return _chapter_dir(manga, chapter) / "pending.json"


def _normalize_stage(source_stage: str) -> str:
    stage = str(source_stage or "").strip().upper()
    if stage == "MERGED":
        stage = "MERGE"
    if stage not in VALID_STAGES:
        raise ValueError("Fonte do Texto Off inválida para o Nível III.")
    return stage


def _validate_image_name(value: str, label: str) -> str:
    name = str(value or "").strip()
    if not name or Path(name).name != name:
        raise ValueError(f"{label} inválida.")
    if Path(name).suffix.lower() not in IMAGE_EXTS:
        raise ValueError(f"{label} não é uma imagem suportada.")
    return name


def _source_dir(manga: Path, chapter: str, stage: str) -> Path:
    return (manga / "IMG" / chapter) if stage == "ORIGINAL" else (manga / "FLUXO_SECUNDARIO" / "02_MERGE" / chapter)


def _clean_dir(manga: Path, chapter: str, stage: str) -> Path:
    folder_stage = "ORIGINAL" if stage == "ORIGINAL" else "MERGED"
    return manga / "FLUXO_SECUNDARIO" / "04_TEXTO_OFF" / folder_stage / chapter


def _load(path: Path) -> dict:
    if not path.is_file():
        return {"schema_version": SCHEMA_VERSION, "items": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Estado do Nível III inválido: {path}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("items", []), list):
        raise ValueError(f"Estado do Nível III inválido: {path}")
    return data


def _atomic_write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=".pending-", suffix=".json", dir=str(path.parent))
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def _item_key(stage: str, source_file: str) -> str:
    return f"{stage}:{source_file}"


def pending_for_chapter(manga: Path, chapter: str) -> dict[str, dict]:
    """Retorna as páginas pendentes indexadas por SOURCE_STAGE:source_file."""
    path = _state_path(manga, chapter)
    if not path.is_file():
        return {}
    data = _load(path)
    out: dict[str, dict] = {}
    for item in data.get("items", []):
        if not isinstance(item, dict):
            continue
        try:
            stage = _normalize_stage(item.get("source_stage"))
            source_file = _validate_image_name(item.get("source_file"), "Imagem original")
        except ValueError:
            continue
        if item.get("status") == STATUS_PENDING:
            out[_item_key(stage, source_file)] = item
    return out


def flag_correction(manga: Path, chapter: str, source_stage: str, source_file: str, clean_file: str) -> dict:
    """Registra uma página para correção assistida sem alterar nenhuma imagem."""
    chapter = str(chapter or "").strip()
    stage = _normalize_stage(source_stage)
    source_file = _validate_image_name(source_file, "Imagem original")
    clean_file = _validate_image_name(clean_file, "Imagem limpa")

    source_path = (_source_dir(manga, chapter, stage) / source_file).resolve()
    clean_path = (_clean_dir(manga, chapter, stage) / clean_file).resolve()
    source_base = _source_dir(manga, chapter, stage).resolve()
    clean_base = _clean_dir(manga, chapter, stage).resolve()

    if not source_path.is_relative_to(source_base) or not source_path.is_file():
        raise ValueError("Imagem original do Texto Off não encontrada.")
    if not clean_path.is_relative_to(clean_base) or not clean_path.is_file():
        raise ValueError("Imagem limpa do Texto Off não encontrada.")

    # Confirm that this exact source/clean pair belongs to the current Cleaner V2 manifest.
    manifest_path = clean_base / "clean-manifest.json"
    if not manifest_path.is_file():
        raise ValueError("Manifesto do Cleaner V2 não encontrado para a página selecionada.")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Manifesto do Cleaner V2 inválido.") from exc
    sources = [str(x) for x in (manifest.get("source_artifacts") or [])]
    cleans = [str(x) for x in (manifest.get("clean_artifacts") or [])]
    if len(sources) != len(cleans) or (source_file, clean_file) not in set(zip(sources, cleans)):
        raise ValueError("A página selecionada não pertence ao resultado atual do Cleaner V2.")

    path = _state_path(manga, chapter)
    data = _load(path)
    items = [x for x in data.get("items", []) if isinstance(x, dict)]
    key = _item_key(stage, source_file)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    existing = None
    for item in items:
        if _item_key(str(item.get("source_stage", "")).upper(), str(item.get("source_file", ""))) == key:
            existing = item
            break

    if existing is None:
        existing = {
            "source_stage": stage,
            "source_file": source_file,
            "clean_file": clean_file,
            "status": STATUS_PENDING,
            "created_at": now,
            "updated_at": now,
        }
        items.append(existing)
    else:
        existing.update({
            "source_stage": stage,
            "source_file": source_file,
            "clean_file": clean_file,
            "status": STATUS_PENDING,
            "updated_at": now,
        })
        existing.setdefault("created_at", now)

    payload = {
        "schema_version": SCHEMA_VERSION,
        "chapter": chapter,
        "items": items,
    }
    _atomic_write(path, payload)
    return {
        "chapter": chapter,
        "source_stage": stage,
        "source_file": source_file,
        "clean_file": clean_file,
        "status": STATUS_PENDING,
        "state_file": str(path),
        "message": "Página sinalizada para correção assistida no Nível III.",
    }


def flag_correction_job(manga: Path, chs, payload: dict) -> list[dict]:
    if len(chs) != 1:
        raise ValueError("O Nível III sinaliza uma página por vez.")
    ch = chs[0]
    return [flag_correction(
        manga,
        ch.name,
        payload.get("source_stage"),
        payload.get("source_file"),
        payload.get("clean_file"),
    )]

def queue_state(manga: Path) -> dict:
    """Lista as páginas pendentes do Nível III sem alterar imagens."""
    import re
    rows = []
    root = _root(manga)
    if root.is_dir():
        dirs = [p for p in root.iterdir() if p.is_dir()]
        dirs.sort(key=lambda p: [int(x) if x.isdigit() else x.lower() for x in re.split(r"(\d+)", p.name)])
        for chapter_dir in dirs:
            chapter = chapter_dir.name
            try:
                pending = pending_for_chapter(manga, chapter)
            except ValueError:
                continue
            for item in pending.values():
                try:
                    stage = _normalize_stage(item.get("source_stage"))
                    source_file = _validate_image_name(item.get("source_file"), "Imagem original")
                    clean_file = _validate_image_name(item.get("clean_file"), "Imagem limpa")
                except ValueError:
                    continue
                if not (_source_dir(manga, chapter, stage) / source_file).is_file(): continue
                if not (_clean_dir(manga, chapter, stage) / clean_file).is_file(): continue
                rows.append({
                    "key": f"{stage}:{chapter}:{source_file}", "chapter": chapter,
                    "source_stage": stage, "source": "Original" if stage == "ORIGINAL" else "Merged",
                    "source_file": source_file, "clean_file": clean_file, "status": STATUS_PENDING,
                    "created_at": item.get("created_at"), "updated_at": item.get("updated_at"),
                })
    return {"schema_version": 1, "status": "ok", "pending": len(rows), "rows": rows}
