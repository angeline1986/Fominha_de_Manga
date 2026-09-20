"""Fluxo isolado para sinalização de casos especiais do Texto Off.

Não executa Cleaner V2, não altera máscaras/resultados oficiais e não promove
artefatos. Apenas registra o caso e preserva snapshots imutáveis para revisão.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os
import shutil
import tempfile

SCHEMA_VERSION = 1
STATUS_PENDING = "PENDENTE_ESPECIAL"
VALID_STAGES = {"ORIGINAL", "MERGE"}
VALID_TYPES = {"TRANSPARENCIA", "COLORIDO_GRADIENTE_TEXTURA"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


def _root(manga: Path) -> Path:
    return manga / "FLUXO_SECUNDARIO" / "04_TEXTO_OFF" / "ESPECIAL"


def _normalize_stage(value: str) -> str:
    stage = str(value or "").strip().upper()
    if stage == "MERGED":
        stage = "MERGE"
    if stage not in VALID_STAGES:
        raise ValueError("Fonte do Texto Off inválida para o fluxo especial.")
    return stage


def _normalize_type(value: str) -> str:
    kind = str(value or "").strip().upper()
    if kind not in VALID_TYPES:
        raise ValueError("Tipo de caso especial inválido.")
    return kind


def _image_name(value: str, label: str) -> str:
    name = str(value or "").strip()
    if not name or Path(name).name != name or Path(name).suffix.lower() not in IMAGE_EXTS:
        raise ValueError(f"{label} inválida.")
    return name


def _chapter(value: str) -> str:
    chapter = str(value or "").strip()
    if not chapter or chapter in {".", ".."} or "/" in chapter or "\\" in chapter:
        raise ValueError("Capítulo inválido para o fluxo especial.")
    return chapter


def _source_dir(manga: Path, chapter: str, stage: str) -> Path:
    return manga / "IMG" / chapter if stage == "ORIGINAL" else manga / "FLUXO_SECUNDARIO" / "02_MERGE" / chapter


def _clean_dir(manga: Path, chapter: str, stage: str) -> Path:
    folder = "ORIGINAL" if stage == "ORIGINAL" else "MERGED"
    return manga / "FLUXO_SECUNDARIO" / "04_TEXTO_OFF" / folder / chapter


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _case_dir(manga: Path, chapter: str, stage: str, source_file: str) -> Path:
    safe_stem = Path(source_file).stem
    return _root(manga) / chapter / f"{stage}__{safe_stem}"


def _atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=".special-", suffix=".json", dir=str(path.parent))
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
            fh.flush(); os.fsync(fh.fileno())
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def special_for_chapter(manga: Path, chapter: str) -> dict[str, dict]:
    root = _root(manga) / str(chapter)
    if not root.is_dir():
        return {}
    out = {}
    for case in root.iterdir():
        manifest_path = case / "special-manifest.json"
        if not manifest_path.is_file():
            continue
        try:
            item = json.loads(manifest_path.read_text(encoding="utf-8"))
            stage = _normalize_stage(item.get("source_stage"))
            source = _image_name(item.get("source_file"), "Imagem fonte")
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            continue
        if item.get("status") == STATUS_PENDING:
            out[f"{stage}:{source}"] = item
    return out


def flag_special(manga: Path, chapter: str, source_stage: str, source_file: str, clean_file: str, special_type: str) -> dict:
    chapter = _chapter(chapter)
    stage = _normalize_stage(source_stage)
    source_file = _image_name(source_file, "Imagem fonte")
    clean_file = _image_name(clean_file, "Imagem limpa")
    special_type = _normalize_type(special_type)

    source_base = _source_dir(manga, chapter, stage).resolve()
    clean_base = _clean_dir(manga, chapter, stage).resolve()
    source_path = (source_base / source_file).resolve()
    clean_path = (clean_base / clean_file).resolve()
    if not source_path.is_relative_to(source_base) or not source_path.is_file():
        raise ValueError("Imagem fonte do Texto Off não encontrada.")
    if not clean_path.is_relative_to(clean_base) or not clean_path.is_file():
        raise ValueError("Resultado oficial do Texto Off não encontrado.")

    manifest_path = clean_base / "clean-manifest.json"
    if not manifest_path.is_file():
        raise ValueError("Manifesto atual do Cleaner V2 não encontrado.")
    try:
        cleaner_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Manifesto atual do Cleaner V2 inválido.") from exc
    pairs = set(zip(
        [str(x) for x in cleaner_manifest.get("source_artifacts") or []],
        [str(x) for x in cleaner_manifest.get("clean_artifacts") or []],
    ))
    if (source_file, clean_file) not in pairs:
        raise ValueError("A página não pertence ao resultado atual do Cleaner V2.")

    case_dir = _case_dir(manga, chapter, stage, source_file)
    refs = case_dir / "reference"
    refs.mkdir(parents=True, exist_ok=True)
    source_ref = refs / f"source{source_path.suffix.lower()}"
    current_ref = refs / f"current{clean_path.suffix.lower()}"
    shutil.copy2(source_path, source_ref)
    shutil.copy2(clean_path, current_ref)

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    payload = {
        "schema_version": SCHEMA_VERSION,
        "status": STATUS_PENDING,
        "chapter": chapter,
        "source_stage": stage,
        "source_file": source_file,
        "clean_file": clean_file,
        "special_type": special_type,
        "region": {"mode": "PAGE", "bbox_pixels": None},
        "created_at": now,
        "updated_at": now,
        "references": {
            "source": str(source_ref.relative_to(case_dir)),
            "current": str(current_ref.relative_to(case_dir)),
            "source_sha256": _sha256(source_ref),
            "current_sha256": _sha256(current_ref),
        },
        "safety": {
            "cleaner_v2_modified": False,
            "level1_modified": False,
            "level2_modified": False,
            "level3_modified": False,
            "official_image_modified": False,
            "promotion_automatic": False,
        },
    }
    _atomic_json(case_dir / "special-manifest.json", payload)
    return {**payload, "case_dir": str(case_dir), "message": "Caso especial sinalizado sem alterar o fluxo oficial."}


def flag_special_job(manga: Path, chs, payload: dict) -> list[dict]:
    if len(chs) != 1:
        raise ValueError("O fluxo especial sinaliza uma página por vez.")
    ch = chs[0]
    return [flag_special(
        manga, ch.name, payload.get("source_stage"), payload.get("source_file"),
        payload.get("clean_file"), payload.get("special_type"),
    )]
