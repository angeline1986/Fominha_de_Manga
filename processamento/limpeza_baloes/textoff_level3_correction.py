"""Texto Off — Nível III: geração segura de preview de correção assistida.

Este módulo NÃO promove correções. A imagem oficial do Texto Off é somente leitura.
A execução do LaMa ocorre no ambiente isolado do Cleaner V2 e a composição final
substitui exclusivamente os pixels da máscara selecionada.
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
    _clean_dir,
    _item_key,
    _normalize_stage,
    _source_dir,
    _validate_image_name,
    pending_for_chapter,
)

SCHEMA = "textoff_level3_proposal_v1"
STATUS = "PROPOSTA_GERADA"
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


def generate_preview(manga: Path, chapter: str, source_stage: str, source_file: str, clean_file: str, selection_raw: object) -> dict:
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
    selection = _selection_percent(selection_raw)

    with Image.open(source_path) as src_im, Image.open(clean_path) as clean_im:
        source_size = tuple(src_im.size)
        clean_size = tuple(clean_im.size)
    if source_size != clean_size:
        raise RuntimeError(f"Dimensões divergentes entre fonte e resultado atual: {source_size} != {clean_size}.")
    width, height = clean_size
    bbox = _bbox_pixels(selection, width, height)

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
            _worker_command(source_path, clean_path, preview_path, report_path, bbox),
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
            "selection_percent": selection,
            "bbox_pixels": {
                "x": bbox[0], "y": bbox[1], "width": bbox[2] - bbox[0], "height": bbox[3] - bbox[1],
            },
            "crop_pixels": worker.get("crop_pixels"),
            "padding": worker.get("padding"),
            "status": STATUS,
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "base_sha256": base_sha256,
            "source_sha256": source_sha256,
            "preview_file": "preview.png",
            "worker": {
                "device": worker.get("device"),
                "model": worker.get("model"),
            },
            "safety": {
                "official_image_modified": False,
                "source_image_modified": False,
                "composition_limited_to_mask": True,
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
            "selection_percent": selection,
            "bbox_pixels": manifest["bbox_pixels"],
            "base_sha256": base_sha256,
            "device": worker.get("device"),
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
        payload.get("clean_file"), payload.get("selection"),
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
