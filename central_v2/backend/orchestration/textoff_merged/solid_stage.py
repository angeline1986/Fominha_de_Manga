"""Solid white stage: execute approved Check ROIs using Laboratory engine."""
from __future__ import annotations
import json
import hashlib
import os
from pathlib import Path
import shutil
import tempfile
from datetime import datetime, timezone
from uuid import uuid4
from PIL import Image
from central_v2.backend.routes.laboratorio_solidos import _filter, _sha
from .auto_cleaner_check_manifest import manifest_path, _read_check_manifest
from .auto_cleaner_check_images import check_image
from .reset_check_override import effective
from .stages import LEVEL1, stage_chapter

STAGE = "05_AUTO_CLEANER_SOLIDOS"
TYPE = "residuo_balao_solido_branco"


def rows_for(manga, document, chapter):
    check = manifest_path(manga, chapter)
    if not check.is_file():
        return [], None
    saved = _read_check_manifest(check, document)
    rows = [r for r in saved["approved_occurrences"] if r.get("tipo") == TYPE]
    return rows, _sha(check)


def decision_sha256(rows):
    selected = [{key: row.get(key) for key in ("id", "page", "tipo", "box_pixels")}
                for row in rows]
    selected.sort(key=lambda row: (row.get("page") or "", row.get("id") or ""))
    payload = json.dumps(selected, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def source_for(manga, chapter, page, expected_sha256=None):
    if not isinstance(page, str) or Path(page).name != page or not page.lower().endswith(".png"):
        raise ValueError("Página inválida no Check")
    folder = stage_chapter(manga, LEVEL1, chapter)
    source = (folder / "clean" / (Path(page).stem + "_clean.png")).resolve()
    if not source.is_relative_to(folder.resolve()) or not source.is_file():
        raise ValueError("Saída original do Auto-Cleaner I indisponível: " + page)
    check = check_image(manga, chapter, page, source)
    current = effective(manga, chapter, page, check)
    if expected_sha256 is not None:
        # Existing previews must retain their own, immutable input version.
        for candidate in (current, check, source):
            if _sha(candidate) == expected_sha256:
                return candidate
        raise ValueError("Fonte histórica da prévia Sólidos indisponível")
    return current


def execute_chapter(manga, document, chapter, *, candidate_pages=None, output_dir=None):
    rows, check_hash = rows_for(manga, document, chapter)
    if not rows:
        raise ValueError("Capítulo sem ocorrências Sólidos aprovadas no Check")
    target = Path(output_dir) if output_dir is not None else stage_chapter(
        manga, STAGE, chapter, read_legacy=False)
    if output_dir is not None and not _disposable_target(manga, target):
        raise ValueError("Destino de staging deve estar em diretório temporário isolado")
    if target.exists():
        raise ValueError("Etapa Sólidos já possui resultados: " + chapter)
    target.parent.mkdir(parents=True, exist_ok=True)
    grouped = {}
    seen = set()
    for row in rows:
        ident, page = row.get("id"), row.get("page")
        if not isinstance(ident, str) or not ident or ident in seen:
            raise ValueError("Identificador de ocorrência inválido/repetido")
        seen.add(ident)
        grouped.setdefault(page, []).append(row)
    if candidate_pages is not None:
        if not isinstance(candidate_pages, (set, list, tuple)):
            raise ValueError("Lista de páginas candidatas inválida")
        grouped = {page: rows for page, rows in grouped.items() if page in candidate_pages}
        if not grouped:
            raise ValueError("Capítulo sem ocorrências Sólidos pendentes")
    sources = {page: source_for(manga, chapter, page) for page in grouped}
    hashes = {page: _sha(path) for page, path in sources.items()}
    scratch = Path(tempfile.mkdtemp(prefix=".solid-stage-", dir=target.parent))
    try:
        (scratch / "clean").mkdir()
        (scratch / "mask").mkdir()
        audit, pages = [], []
        run_id = uuid4().hex
        created_at = datetime.now(timezone.utc).isoformat()
        for page, selections in sorted(grouped.items()):
            source = sources[page]
            with Image.open(source) as img:
                original = img.convert("RGB")
            if original.width * original.height > 100_000_000:
                raise ValueError("Imagem excede limite operacional")
            boxes = []
            for row in selections:
                data = row.get("box_pixels")
                if not isinstance(data, dict):
                    raise ValueError("ROI inválida no Check")
                vals = [data.get(k) for k in ("x", "y", "width", "height")]
                if any(type(v) is not int for v in vals):
                    raise ValueError("Coordenadas da ROI inválidas")
                boxes.append(dict(zip(("x", "y", "width", "height"), vals)))
            result, mask, decisions = _filter(original, boxes)
            if _sha(source) != hashes[page] or _sha(manifest_path(manga, chapter)) != check_hash:
                raise ValueError("Fonte ou Check alterados durante execução")
            filename = Path(page).stem + "_clean.png"
            result.save(scratch / "clean" / filename)
            mask.save(scratch / "mask" / (Path(page).stem + "_mask.png"))
            for row, decision in zip(selections, decisions):
                audit.append({"id": row["id"], "page": page, **decision})
            pages.append({"page": page, "run_id": run_id, "created_at": created_at,
                          "decision_sha256": decision_sha256(selections),
                          "check_sha256": check_hash, "source_sha256": hashes[page],
                          "result_sha256": _sha(scratch / "clean" / filename),
                          "mask_sha256": _sha(scratch / "mask" / (Path(page).stem + "_mask.png"))})
        if any(_sha(path) != hashes[page] for page, path in sources.items()):
            raise ValueError("Fonte alterada antes da publicação")
        if _sha(manifest_path(manga, chapter)) != check_hash:
            raise ValueError("Check alterado antes da publicação")
        manifest = {"schema": "textoff_solid_stage_v1", "provider": document["provider"],
                    "manga": document["obra"], "chapter": chapter,
                    "run_id": run_id, "created_at": created_at,
                    "motor": "laboratorio_solidos._filter", "check_sha256": check_hash,
                    "preview_only": True, "pages": pages, "regions": audit}
        (scratch / "solid-white-manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if target.exists():
            raise ValueError("Resultados criados simultaneamente; nada sobrescrito")
        os.rename(scratch, target)
        return {"chapter": chapter, "pages": len(pages), "regions": len(audit),
                "candidates": sum(r.get("changed_pixels", 0) for r in audit)}
    finally:
        if scratch.exists():
            shutil.rmtree(scratch, ignore_errors=True)


def _disposable_target(manga, target):
    resolved = Path(target).resolve()
    temporary_roots = {Path(tempfile.gettempdir()).resolve(), Path("/tmp").resolve(),
                       Path("/private/tmp").resolve()}
    return (not resolved.is_relative_to(Path(manga).resolve())
            and any(resolved.is_relative_to(root) for root in temporary_roots))
