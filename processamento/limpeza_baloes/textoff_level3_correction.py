"""Texto Off — Nível III: preview e promoção segura da correção assistida.

A geração de preview nunca altera imagens oficiais. Somente uma aprovação explícita
pode promover a proposta validada. Para source_stage=MERGE, a aprovação atualiza
tanto o resultado do Texto Off quanto o arquivo correspondente em 02_MERGE; IMG
permanece imutável para source_stage=ORIGINAL. O LaMa continua isolado no Cleaner V2.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import uuid

from PIL import Image

from processamento.limpeza_baloes.textoff_level3 import (
    STATUS_PENDING,
    _clean_dir,
    _item_key,
    _load,
    _normalize_stage,
    _source_dir,
    _state_path,
    _validate_image_name,
    pending_for_chapter,
)
SCHEMA = "textoff_level3_proposal_v1"

REGIONAL_ROOT = (
    Path(__file__).resolve().parent
    / "level3_regional"
)

REGIONAL_PYTHON = (
    REGIONAL_ROOT
    / ".venv"
    / "bin"
    / "python"
)

REGIONAL_WORKER = (
    REGIONAL_ROOT
    / "regional.py"
)

REGIONAL_MODEL = (
    Path.home()
    / "Library"
    / "Caches"
    / "pcleaner"
    / "model"
    / "anime-manga-big-lama.pt"
)
STATUS = "PROPOSTA_GERADA"
STATUS_APPROVED = "APROVADA"
STATUS_CORRECTED = "CORRIGIDO_NIVEL3"
MASK_MARGIN_RATIO = 0.15
MASK_MARGIN_MIN = 16
MASK_MARGIN_MAX = 64
PROPOSAL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
ROOT = Path(__file__).resolve().parents[2]
CLEANER_VENV_PYTHON = ROOT / "processamento" / "limpeza_baloes" / "cleaner_v2" / ".venv" / "bin" / "python"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _chapter_name(value: object) -> str:
    chapter = str(value or "").strip()
    if not chapter or chapter in {".", ".."} or "/" in chapter or "\\" in chapter:
        raise ValueError("Capítulo inválido para o Nível III.")
    return chapter


def _proposals_root(manga: Path, chapter: str) -> Path:
    return manga / "FLUXO_SECUNDARIO" / "04_TEXTO_OFF" / "NIVEL3" / _chapter_name(chapter) / "proposals"


def proposal_dir(manga: Path, chapter: str, proposal_id: str) -> Path:
    pid = str(proposal_id or "").strip()
    if not PROPOSAL_RE.fullmatch(pid):
        raise ValueError("Identificador de proposta do Nível III inválido.")
    base = _proposals_root(manga, chapter).resolve()
    target = (base / pid).resolve()
    if not target.is_relative_to(base):
        raise ValueError("Caminho da proposta do Nível III inválido.")
    return target


def _selection_percent(value: object) -> dict[str, float]:
    if not isinstance(value, dict):
        raise ValueError("Seleção manual ausente para gerar a prévia.")
    out: dict[str, float] = {}
    for key in ("left", "top", "width", "height"):
        try:
            number = float(value.get(key))
        except (TypeError, ValueError):
            raise ValueError(f"Seleção manual inválida: {key}.") from None
        if not math.isfinite(number):
            raise ValueError(f"Seleção manual inválida: {key}.")
        out[key] = number
    if out["left"] < 0 or out["top"] < 0 or out["width"] <= 0 or out["height"] <= 0:
        raise ValueError("Seleção manual possui coordenadas ou dimensões inválidas.")
    if out["left"] + out["width"] > 100.000001 or out["top"] + out["height"] > 100.000001:
        raise ValueError("Seleção manual ultrapassa os limites da imagem.")
    return out


def _bbox_pixels(selection: dict[str, float], width: int, height: int) -> tuple[int, int, int, int]:
    x1 = max(0, min(width, math.floor(selection["left"] / 100.0 * width)))
    y1 = max(0, min(height, math.floor(selection["top"] / 100.0 * height)))
    x2 = max(0, min(width, math.ceil((selection["left"] + selection["width"]) / 100.0 * width)))
    y2 = max(0, min(height, math.ceil((selection["top"] + selection["height"]) / 100.0 * height)))
    if x2 <= x1 or y2 <= y1:
        raise ValueError("Seleção manual resulta em uma área vazia na imagem real.")
    return x1, y1, x2, y2


def _mask_bbox_pixels(bbox: tuple[int, int, int, int], width: int, height: int) -> tuple[tuple[int, int, int, int], int]:
    x1, y1, x2, y2 = bbox
    margin = int(round(min(x2 - x1, y2 - y1) * MASK_MARGIN_RATIO))
    margin = max(MASK_MARGIN_MIN, min(MASK_MARGIN_MAX, margin))
    mask_bbox = (max(0, x1-margin), max(0, y1-margin), min(width, x2+margin), min(height, y2+margin))
    return mask_bbox, margin


def _validate_current_pair(manga: Path, chapter: str, stage: str, source_file: str, clean_file: str) -> tuple[Path, Path]:
    source_base = _source_dir(manga, chapter, stage).resolve()
    clean_base = _clean_dir(manga, chapter, stage).resolve()
    source_path = (source_base / source_file).resolve()
    clean_path = (clean_base / clean_file).resolve()
    if not source_path.is_relative_to(source_base) or not source_path.is_file():
        raise ValueError("Imagem original do Texto Off não encontrada.")
    if not clean_path.is_relative_to(clean_base) or not clean_path.is_file():
        raise ValueError("Resultado atual do Texto Off não encontrado.")

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
    return source_path, clean_path


def _worker_command(source_path: Path, clean_path: Path, preview_path: Path, report_path: Path, bbox: tuple[int, int, int, int]) -> list[str]:
    if not CLEANER_VENV_PYTHON.is_file():
        raise RuntimeError(f"Python isolado do Cleaner V2 não encontrado: {CLEANER_VENV_PYTHON}")
    return [
        str(CLEANER_VENV_PYTHON), str(Path(__file__).resolve()), "--worker",
        "--source", str(source_path), "--clean", str(clean_path),
        "--preview", str(preview_path), "--report", str(report_path),
        "--bbox", ",".join(str(x) for x in bbox),
    ]



def _regional_worker_command(
    source_path: Path,
    clean_path: Path,
    preview_path: Path,
    report_path: Path,
    bboxes: list[tuple[int, int, int, int]],
) -> list[str]:
    if not REGIONAL_PYTHON.is_file():
        raise RuntimeError(
            "Python isolado da Correção Assistida Regional "
            f"não encontrado: {REGIONAL_PYTHON}"
        )

    if not REGIONAL_WORKER.is_file():
        raise RuntimeError(
            "Worker da Correção Assistida Regional "
            f"não encontrado: {REGIONAL_WORKER}"
        )

    if not REGIONAL_MODEL.is_file():
        raise RuntimeError(
            f"Modelo LaMa não encontrado: {REGIONAL_MODEL}"
        )

    command = [
        str(REGIONAL_PYTHON),
        str(REGIONAL_WORKER),
        "--source", str(source_path),
        "--clean", str(clean_path),
        "--output", str(preview_path),
        "--report", str(report_path),
        "--model", str(REGIONAL_MODEL),
    ]

    for bbox in bboxes:
        command.extend([
            "--bbox",
            ",".join(str(value) for value in bbox),
        ])

    return command


def _selections_percent(value: object) -> list[dict]:
    if isinstance(value, dict):
        values = [value]
    elif isinstance(value, list):
        values = value
    else:
        raise ValueError(
            "Nenhuma área manual válida foi informada."
        )

    if not values:
        raise ValueError(
            "Nenhuma área manual foi informada."
        )

    return [
        _selection_percent(item)
        for item in values
    ]

def generate_preview(manga: Path, chapter: str, source_stage: str, source_file: str, clean_file: str, selections_raw: object) -> dict:
    chapter = _chapter_name(chapter)
    stage = _normalize_stage(source_stage)
    source_file = _validate_image_name(source_file, "Imagem original")
    clean_file = _validate_image_name(clean_file, "Imagem limpa")

    pending = pending_for_chapter(manga, chapter)
    item = pending.get(_item_key(stage, source_file))
    if not item:
        raise ValueError("A página não está pendente de correção assistida no Nível III.")
    if str(item.get("clean_file") or "") != clean_file:
        raise ValueError("O resultado atual informado não corresponde à pendência do Nível III.")

    source_path, clean_path = _validate_current_pair(manga, chapter, stage, source_file, clean_file)
    selections = _selections_percent(selections_raw)

    with Image.open(source_path) as src_im, Image.open(clean_path) as clean_im:
        source_size = tuple(src_im.size)
        clean_size = tuple(clean_im.size)
    if source_size != clean_size:
        raise RuntimeError(f"Dimensões divergentes entre fonte e resultado atual: {source_size} != {clean_size}.")
    width, height = clean_size
    bboxes = [
        _bbox_pixels(selection, width, height)
        for selection in selections
    ]

    base_sha256 = _sha256(clean_path)
    source_sha256 = _sha256(source_path)
    proposal_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f") + "_" + uuid.uuid4().hex[:8]
    proposals_root = _proposals_root(manga, chapter)
    proposals_root.mkdir(parents=True, exist_ok=True)
    final_dir = proposal_dir(manga, chapter, proposal_id)
    if final_dir.exists():
        raise RuntimeError("Colisão inesperada no identificador da proposta.")
    tmp_dir = Path(tempfile.mkdtemp(prefix=".proposal-", dir=str(proposals_root)))
    preview_path = tmp_dir / "preview.png"
    report_path = tmp_dir / "worker-report.json"

    try:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
        proc = subprocess.run(
            _regional_worker_command(
                source_path,
                clean_path,
                preview_path,
                report_path,
                bboxes,
            ),
            cwd=str(ROOT), env=env, text=True, capture_output=True, check=False,
        )
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "").strip()
            raise RuntimeError(f"Falha ao gerar preview com LaMa: {detail[-1200:] or 'worker sem diagnóstico'}")
        if not preview_path.is_file() or not report_path.is_file():
            raise RuntimeError("Worker do Nível III não produziu os artefatos esperados.")
        worker = json.loads(report_path.read_text(encoding="utf-8"))

        if _sha256(clean_path) != base_sha256:
            raise RuntimeError("O resultado oficial do Texto Off foi alterado durante a geração da prévia.")
        if _sha256(source_path) != source_sha256:
            raise RuntimeError("A imagem fonte foi alterada durante a geração da prévia.")

        manifest = {
            "schema": SCHEMA,
            "proposal_id": proposal_id,
            "chapter": chapter,
            "source_stage": stage,
            "source_file": source_file,
            "clean_file": clean_file,
            "origin": "MANUAL",
            "selection_percent": selections[0] if len(selections) == 1 else None,
            "selections_percent": selections,
            "bbox_pixels": (
                {
                    "x": bboxes[0][0],
                    "y": bboxes[0][1],
                    "width": bboxes[0][2] - bboxes[0][0],
                    "height": bboxes[0][3] - bboxes[0][1],
                }
                if len(bboxes) == 1
                else None
            ),
            "bboxes_pixels": [
                {
                    "x": bbox[0],
                    "y": bbox[1],
                    "width": bbox[2] - bbox[0],
                    "height": bbox[3] - bbox[1],
                }
                for bbox in bboxes
            ],
            "regional": {
                "algorithm": worker.get("algorithm"),
                "selection_count": worker.get("selection_count"),
                "mask_pixels": worker.get("mask_pixels"),
                "outside_mask_changed_pixels": worker.get(
                    "outside_mask_changed_pixels"
                ),
                "work_bbox_pixels": worker.get("work_bbox_pixels"),
                "regions": worker.get("regions"),
                "context_padding": worker.get("context_padding"),
            },
            "status": STATUS,
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "base_sha256": base_sha256,
            "source_sha256": source_sha256,
            "preview_file": "preview.png",
            "worker": {
                "device": worker.get("device"),
                "model": worker.get("model"),
                "algorithm": worker.get("algorithm"),
            },
            "safety": {
                "official_image_modified": False,
                "source_image_modified": False,
                "composition_limited_to_mask": True,
                "mask_expands_manual_selection": False,
                "regional_mask_inside_manual_selections": True,
                "outside_mask_changed_pixels": worker.get(
                    "outside_mask_changed_pixels"
                ),
            },
        }
        report_path.unlink(missing_ok=True)
        (tmp_dir / "proposal.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp_dir, final_dir)
        return {
            "status": STATUS,
            "proposal_id": proposal_id,
            "chapter": chapter,
            "source_stage": stage,
            "source_file": source_file,
            "clean_file": clean_file,
            "preview_file": "preview.png",
            "selection_percent": manifest["selection_percent"],
            "selections_percent": selections,
            "bbox_pixels": manifest["bbox_pixels"],
            "bboxes_pixels": manifest["bboxes_pixels"],
            "base_sha256": base_sha256,
            "device": worker.get("device"),
            "algorithm": worker.get("algorithm"),
            "mask_pixels": worker.get("mask_pixels"),
            "outside_mask_changed_pixels": worker.get(
                "outside_mask_changed_pixels"
            ),
            "message": "Prévia do Nível III gerada sem alterar a imagem oficial.",
        }
    except Exception:
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir, ignore_errors=True)
        raise


def generate_preview_job(manga: Path, chs, payload: dict) -> dict:
    if len(chs) != 1:
        raise ValueError("O Nível III gera a prévia de uma página por vez.")
    ch = chs[0]
    requested = str(payload.get("chapter") or ch.name).strip()
    if requested != str(ch.name):
        raise ValueError("Capítulo do payload não corresponde ao capítulo selecionado.")
    return generate_preview(
        manga, ch.name, payload.get("source_stage"), payload.get("source_file"),
        payload.get("clean_file"),
        (
            payload.get("selections")
            if payload.get("selections") is not None
            else payload.get("selection")
        ),
    )


def _json_temp(path: Path, data: dict, prefix: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=prefix, suffix=".json", dir=str(path.parent))
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        return tmp
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


def _restore_bytes(path: Path, raw: bytes, prefix: str) -> None:
    fd, tmp_name = tempfile.mkstemp(prefix=prefix, suffix=path.suffix or ".tmp", dir=str(path.parent))
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(raw)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def approve_proposal(
    manga: Path,
    chapter: str,
    source_stage: str,
    source_file: str,
    clean_file: str,
    proposal_id: str,
) -> dict:
    chapter = _chapter_name(chapter)
    stage = _normalize_stage(source_stage)
    source_file = _validate_image_name(source_file, "Imagem original")
    clean_file = _validate_image_name(clean_file, "Imagem limpa")

    pdir = proposal_dir(manga, chapter, proposal_id)
    manifest_path = (pdir / "proposal.json").resolve()
    pdir_resolved = pdir.resolve()
    if not manifest_path.is_relative_to(pdir_resolved) or not manifest_path.is_file():
        raise ValueError("Manifesto da proposta do Nível III não encontrado.")

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Manifesto da proposta do Nível III inválido.") from exc
    if not isinstance(manifest, dict) or manifest.get("schema") != SCHEMA:
        raise ValueError("Schema da proposta do Nível III não suportado.")
    if str(manifest.get("status") or "") != STATUS:
        raise ValueError("A proposta não está disponível para aprovação.")
    if str(manifest.get("proposal_id") or "") != str(proposal_id):
        raise ValueError("Identificador da proposta divergente.")
    if str(manifest.get("chapter") or "") != chapter:
        raise ValueError("Capítulo da proposta divergente.")
    if _normalize_stage(manifest.get("source_stage")) != stage:
        raise ValueError("Fonte da proposta divergente.")
    if str(manifest.get("source_file") or "") != source_file:
        raise ValueError("Imagem fonte da proposta divergente.")
    if str(manifest.get("clean_file") or "") != clean_file:
        raise ValueError("Resultado oficial da proposta divergente.")

    pending = pending_for_chapter(manga, chapter)
    pending_item = pending.get(_item_key(stage, source_file))
    if not pending_item or str(pending_item.get("clean_file") or "") != clean_file:
        raise ValueError("A página não está mais pendente para esta proposta do Nível III.")

    source_path, clean_path = _validate_current_pair(manga, chapter, stage, source_file, clean_file)
    promote_merge = stage == "MERGE"
    expected_base = str(manifest.get("base_sha256") or "")
    expected_source = str(manifest.get("source_sha256") or "")
    if not expected_base or _sha256(clean_path) != expected_base:
        raise RuntimeError("PROPOSTA_OBSOLETA: o resultado oficial do Texto Off mudou após a geração da prévia.")
    if not expected_source or _sha256(source_path) != expected_source:
        raise RuntimeError("PROPOSTA_OBSOLETA: a imagem fonte mudou após a geração da prévia.")

    preview_file = _validate_image_name(manifest.get("preview_file"), "Preview")
    preview_path = (pdir / preview_file).resolve()
    if not preview_path.is_relative_to(pdir_resolved) or not preview_path.is_file():
        raise ValueError("Preview da proposta do Nível III não encontrado.")

    with Image.open(preview_path) as preview_im, Image.open(clean_path) as clean_im, Image.open(source_path) as source_im:
        preview_size = tuple(preview_im.size)
        clean_size = tuple(clean_im.size)
        source_size = tuple(source_im.size)
    if preview_size != clean_size:
        raise RuntimeError(
            f"Dimensões divergentes entre preview e resultado oficial: {preview_size} != {clean_size}."
        )
    if promote_merge and preview_size != source_size:
        raise RuntimeError(
            f"Dimensões divergentes entre preview e 02_MERGE: {preview_size} != {source_size}."
        )

    preview_sha256 = _sha256(preview_path)
    state_path = _state_path(manga, chapter)
    if not state_path.is_file():
        raise ValueError("Estado pendente do Nível III não encontrado.")
    original_state_bytes = state_path.read_bytes()
    original_manifest_bytes = manifest_path.read_bytes()
    state = _load(state_path)
    items = [x for x in state.get("items", []) if isinstance(x, dict)]
    key = _item_key(stage, source_file)
    state_item = None
    for candidate in items:
        try:
            candidate_stage = _normalize_stage(candidate.get("source_stage"))
            candidate_source = _validate_image_name(candidate.get("source_file"), "Imagem original")
        except ValueError:
            continue
        if _item_key(candidate_stage, candidate_source) == key:
            state_item = candidate
            break
    if state_item is None or state_item.get("status") != STATUS_PENDING:
        raise ValueError("Pendência do Nível III não está disponível para aprovação.")
    if str(state_item.get("clean_file") or "") != clean_file:
        raise ValueError("Resultado oficial da pendência diverge da proposta.")

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    clean_target = str(clean_path.relative_to(manga))
    merge_target = str(source_path.relative_to(manga)) if promote_merge else None
    promoted_targets = [clean_target] + ([merge_target] if merge_target else [])

    state_item.update({
        "status": STATUS_CORRECTED,
        "proposal_id": str(proposal_id),
        "approved_at": now,
        "approved_sha256": preview_sha256,
        "promoted_targets": promoted_targets,
        "updated_at": now,
    })
    state["schema_version"] = state.get("schema_version") or 1
    state["chapter"] = chapter
    state["items"] = items

    manifest["status"] = STATUS_APPROVED
    manifest["approved_at"] = now
    manifest["promoted_to"] = clean_target
    manifest["promoted_sha256"] = preview_sha256
    manifest["promoted_targets"] = promoted_targets
    manifest["promotion"] = {
        "target": clean_target,
        "clean_target": clean_target,
        "merge_target": merge_target,
        "targets": promoted_targets,
        "approved_at": now,
        "promoted_sha256": preview_sha256,
        "source_image_modified": promote_merge,
    }
    safety = manifest.setdefault("safety", {})
    safety["official_image_modified"] = True
    safety["source_image_modified"] = promote_merge
    safety["merge_source_promoted"] = promote_merge
    safety["original_img_modified"] = False
    safety["promotion_requires_explicit_approval"] = True

    clean_backup = None
    source_backup = None
    clean_tmp = None
    source_tmp = None
    state_tmp = None
    manifest_tmp = None
    clean_replaced = False
    source_replaced = False
    state_replaced = False
    manifest_replaced = False
    try:
        fd, backup_name = tempfile.mkstemp(
            prefix=".textoff-l3-before-", suffix=clean_path.suffix, dir=str(clean_path.parent)
        )
        os.close(fd)
        clean_backup = Path(backup_name)
        shutil.copy2(clean_path, clean_backup)

        if promote_merge:
            fd, source_backup_name = tempfile.mkstemp(
                prefix=".textoff-l3-merge-before-", suffix=source_path.suffix, dir=str(source_path.parent)
            )
            os.close(fd)
            source_backup = Path(source_backup_name)
            shutil.copy2(source_path, source_backup)

        fd, promote_name = tempfile.mkstemp(
            prefix=".textoff-l3-promote-", suffix=clean_path.suffix, dir=str(clean_path.parent)
        )
        os.close(fd)
        clean_tmp = Path(promote_name)
        shutil.copy2(preview_path, clean_tmp)

        if promote_merge:
            fd, source_promote_name = tempfile.mkstemp(
                prefix=".textoff-l3-merge-promote-", suffix=source_path.suffix, dir=str(source_path.parent)
            )
            os.close(fd)
            source_tmp = Path(source_promote_name)
            shutil.copy2(preview_path, source_tmp)

        state_tmp = _json_temp(state_path, state, ".textoff-l3-state-")
        manifest_tmp = _json_temp(manifest_path, manifest, ".textoff-l3-proposal-")

        if _sha256(clean_path) != expected_base or _sha256(source_path) != expected_source:
            raise RuntimeError("PROPOSTA_OBSOLETA: os arquivos mudaram durante a preparação da aprovação.")

        os.replace(clean_tmp, clean_path)
        clean_tmp = None
        clean_replaced = True
        if _sha256(clean_path) != preview_sha256:
            raise RuntimeError("Falha de integridade ao promover o preview para o Texto Off oficial.")

        if promote_merge:
            os.replace(source_tmp, source_path)
            source_tmp = None
            source_replaced = True
            if _sha256(source_path) != preview_sha256:
                raise RuntimeError("Falha de integridade ao promover o preview para 02_MERGE.")

        os.replace(state_tmp, state_path)
        state_tmp = None
        state_replaced = True

        os.replace(manifest_tmp, manifest_path)
        manifest_tmp = None
        manifest_replaced = True

        if _sha256(clean_path) != preview_sha256:
            raise RuntimeError("O resultado oficial divergiu após a aprovação; rollback acionado.")
        if promote_merge:
            if _sha256(source_path) != preview_sha256:
                raise RuntimeError("A imagem em 02_MERGE divergiu após a aprovação; rollback acionado.")
        elif _sha256(source_path) != expected_source:
            raise RuntimeError("A imagem original mudou durante a aprovação; rollback acionado.")
    except Exception:
        rollback_errors = []
        try:
            if source_replaced and source_backup and source_backup.is_file():
                os.replace(source_backup, source_path)
                source_backup = None
        except Exception as exc:
            rollback_errors.append(f"imagem 02_MERGE: {exc}")
        try:
            if clean_replaced and clean_backup and clean_backup.is_file():
                os.replace(clean_backup, clean_path)
                clean_backup = None
        except Exception as exc:
            rollback_errors.append(f"imagem oficial Texto Off: {exc}")
        try:
            if state_replaced:
                _restore_bytes(state_path, original_state_bytes, ".textoff-l3-state-rollback-")
        except Exception as exc:
            rollback_errors.append(f"pending.json: {exc}")
        try:
            if manifest_replaced:
                _restore_bytes(manifest_path, original_manifest_bytes, ".textoff-l3-proposal-rollback-")
        except Exception as exc:
            rollback_errors.append(f"proposal.json: {exc}")
        if rollback_errors:
            raise RuntimeError("Falha na aprovação e no rollback: " + " | ".join(rollback_errors))
        raise
    finally:
        for tmp in (clean_tmp, source_tmp, state_tmp, manifest_tmp):
            if isinstance(tmp, Path):
                tmp.unlink(missing_ok=True)
        if clean_backup is not None:
            clean_backup.unlink(missing_ok=True)
        if source_backup is not None:
            source_backup.unlink(missing_ok=True)

    message = "Correção Nível III aprovada. O resultado oficial do Texto Off foi atualizado."
    if promote_merge:
        message += " O arquivo correspondente em 02_MERGE também foi atualizado."
    else:
        message += " A imagem original em IMG permaneceu inalterada."

    return {
        "status": STATUS_APPROVED,
        "proposal_id": str(proposal_id),
        "chapter": chapter,
        "source_stage": stage,
        "source_file": source_file,
        "clean_file": clean_file,
        "promoted_to": clean_target,
        "promoted_targets": promoted_targets,
        "merge_promoted_to": merge_target,
        "promoted_sha256": preview_sha256,
        "source_image_modified": promote_merge,
        "message": message,
    }

def approve_proposal_job(manga: Path, chs, payload: dict) -> dict:
    if len(chs) != 1:
        raise ValueError("O Nível III aprova uma página por vez.")
    ch = chs[0]
    requested = str(payload.get("chapter") or ch.name).strip()
    if requested != str(ch.name):
        raise ValueError("Capítulo do payload não corresponde ao capítulo selecionado.")
    return approve_proposal(
        manga,
        ch.name,
        payload.get("source_stage"),
        payload.get("source_file"),
        payload.get("clean_file"),
        payload.get("proposal_id"),
    )


def _worker(source: Path, clean: Path, preview: Path, report: Path, bbox: tuple[int, int, int, int]) -> int:
    # Imports pesados existem somente no ambiente isolado do Cleaner V2.
    import numpy as np
    import torch
    from simple_lama_inpainting import SimpleLama
    from processamento.limpeza_baloes.cleaner_v2.level2 import PADDING, _find_model

    original = Image.open(source).convert("RGB")
    current = Image.open(clean).convert("RGB")
    if original.size != current.size:
        raise RuntimeError(f"Dimensões divergentes no worker: original={original.size}, atual={current.size}")
    width, height = original.size
    x1, y1, x2, y2 = bbox
    if not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height):
        raise ValueError("BBox inválida para as dimensões reais da imagem.")

    cx1 = max(0, x1 - int(PADDING)); cy1 = max(0, y1 - int(PADDING))
    cx2 = min(width, x2 + int(PADDING)); cy2 = min(height, y2 + int(PADDING))
    original_np = np.asarray(original)
    current_np = np.asarray(current).copy()
    original_crop = Image.fromarray(original_np[cy1:cy2, cx1:cx2])

    local_mask = np.zeros((cy2 - cy1, cx2 - cx1), dtype=np.uint8)
    local_mask[y1 - cy1:y2 - cy1, x1 - cx1:x2 - cx1] = 255
    mask_img = Image.fromarray(local_mask, mode="L")

    model_path = _find_model()
    os.environ["LAMA_MODEL"] = str(model_path)
    device = torch.device("mps") if torch.backends.mps.is_available() else torch.device("cpu")
    model = SimpleLama(device=device)
    result = model(original_crop, mask_img)
    if result.size != original_crop.size:
        result = result.crop((0, 0, original_crop.width, original_crop.height))
    result_np = np.asarray(result)
    local = local_mask > 0
    if result_np.shape[:2] != local.shape:
        raise RuntimeError(f"Saída LaMa incompatível: lama={result_np.shape[:2]}, mask={local.shape}")

    target = current_np[cy1:cy2, cx1:cx2]
    target[local] = result_np[local]
    current_np[cy1:cy2, cx1:cx2] = target
    preview.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(current_np).save(preview, "PNG")
    report.write_text(json.dumps({
        "device": str(device), "model": str(model_path), "padding": int(PADDING),
        "crop_pixels": {"x": cx1, "y": cy1, "width": cx2-cx1, "height": cy2-cy1},
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


def _parse_bbox(raw: str) -> tuple[int, int, int, int]:
    try:
        values = tuple(int(x) for x in str(raw).split(","))
    except ValueError:
        raise argparse.ArgumentTypeError("BBox inválida.") from None
    if len(values) != 4:
        raise argparse.ArgumentTypeError("BBox deve possuir quatro inteiros.")
    return values


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--source", type=Path)
    parser.add_argument("--clean", type=Path)
    parser.add_argument("--preview", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--bbox", type=_parse_bbox)
    args = parser.parse_args()
    if not args.worker:
        parser.error("Este módulo não possui execução direta fora do modo worker.")
    for name in ("source", "clean", "preview", "report", "bbox"):
        if getattr(args, name) is None:
            parser.error(f"--{name} é obrigatório no modo worker.")
    return _worker(args.source, args.clean, args.preview, args.report, args.bbox)


if __name__ == "__main__":
    raise SystemExit(main())
