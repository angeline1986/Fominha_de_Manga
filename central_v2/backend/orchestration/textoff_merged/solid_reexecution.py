"""Page-scoped, recoverable reexecution for the preview-only Solid stage."""
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import shutil
import tempfile
from uuid import uuid4
from PIL import Image

from central_v2.backend.routes.laboratorio_solidos import _sha
from .auto_cleaner_check_manifest import manifest_path as check_manifest_path
from .solid_stage import STAGE, decision_sha256, execute_chapter, rows_for, source_for
from .stages import stage_chapter


@contextmanager
def _solid_lock(folder):
    lock_path = folder.parent / ".solid-stage-reexecution.lock"
    with lock_path.open("a+b") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def reexecute_page(manga, document, chapter, page, expected_result_sha256):
    if (not isinstance(page, str) or Path(page).name != page
            or not page.lower().endswith(".png")):
        raise ValueError("Página inválida para reexecução Sólidos.")
    target = stage_chapter(manga, STAGE, chapter, read_legacy=False).resolve()
    if not target.is_relative_to(Path(manga).resolve()) or not target.is_dir():
        raise ValueError("Prévia anterior de Sólidos indisponível para reexecução.")
    with _solid_lock(target):
        return _reexecute_locked(manga, document, chapter, page,
                                 expected_result_sha256, target)


def _reexecute_locked(manga, document, chapter, page, expected_result_sha256, target):
    manifest_path = target / "solid-white-manifest.json"
    previous = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (previous.get("schema") != "textoff_solid_stage_v1"
            or previous.get("provider") != document.get("provider")
            or previous.get("manga") != document.get("obra")
            or previous.get("chapter") != chapter
            or previous.get("preview_only") is not True):
        raise ValueError("Manifesto anterior de Sólidos incompatível.")
    old_page = next((row for row in previous.get("pages", [])
                     if isinstance(row, dict) and row.get("page") == page), None)
    if not old_page or old_page.get("result_sha256") != expected_result_sha256:
        raise ValueError("A prévia mudou desde a consulta; atualize a lista antes de reexecutar.")
    old_regions = [row for row in previous.get("regions", [])
                   if isinstance(row, dict) and row.get("page") == page]
    rows, check_hash = rows_for(manga, {**document, "capitulo": chapter}, chapter)
    page_rows = [row for row in rows if row.get("page") == page]
    with tempfile.TemporaryDirectory(prefix=".solid-page-run-") as run_folder:
        run_target = Path(run_folder) / "result"
        if page_rows:
            execute_chapter(manga, {**document, "capitulo": chapter}, chapter,
                            candidate_pages=[page], output_dir=run_target)
        else:
            _write_unchanged_page(manga, document, chapter, page, check_hash, run_target)
        fresh = json.loads((run_target / "solid-white-manifest.json").read_text(encoding="utf-8"))
        new_page = next((row for row in fresh.get("pages", [])
                         if isinstance(row, dict) and row.get("page") == page), None)
        if not new_page:
            raise ValueError("A reexecução não gerou resultado para a página selecionada.")
        return _publish_page(manga, document, chapter, target, run_target,
                             previous, old_page, old_regions, fresh, new_page, page,
                             check_hash)


def _publish_page(manga, document, chapter, target, run_target, previous,
                  old_page, old_regions, fresh, new_page, page, check_hash):
    for kind, suffix, digest_key in (("clean", "_clean.png", "result_sha256"),
                                     ("mask", "_mask.png", "mask_sha256")):
        filename = Path(page).stem + suffix
        source = target / kind / filename
        if not source.is_file() or _sha(source) != old_page.get(digest_key):
            raise ValueError("A prévia anterior da página está ausente ou divergente.")

    run_id = uuid4().hex
    created_at = datetime.now(timezone.utc).isoformat()
    new_page = {**new_page, "run_id": run_id, "created_at": created_at}
    record = json.loads(json.dumps(previous))
    history = record.setdefault("superseded_pages", [])
    if not isinstance(history, list):
        raise ValueError("Histórico de reexecução Sólidos inválido.")
    archive_id = uuid4().hex
    history.append({"run_id": old_page.get("run_id"), "archive_id": archive_id,
        "replaced_by": run_id, "page": page, "created_at": old_page.get("created_at"),
        "superseded_at": created_at,
        "check_sha256": old_page.get("check_sha256", previous.get("check_sha256")),
        "decision_sha256": old_page.get("decision_sha256"),
        "source_sha256": old_page.get("source_sha256"),
        "result_sha256": old_page.get("result_sha256"),
        "mask_sha256": old_page.get("mask_sha256"), "regions": old_regions})

    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".solid-page-publish-", dir=target.parent) as work:
        staged = Path(work) / "stage"
        shutil.copytree(target, staged)
        archive = staged / "history" / archive_id
        for kind, suffix in (("clean", "_clean.png"), ("mask", "_mask.png")):
            filename = Path(page).stem + suffix
            archived = archive / kind / filename
            archived.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(target / kind / filename, archived)
            active_source = run_target / kind / filename
            active_target = staged / kind / filename
            if not active_source.is_file():
                raise ValueError("A nova prévia da página está incompleta.")
            shutil.copyfile(active_source, active_target)

        old_pages = record.get("pages", [])
        if not isinstance(old_pages, list) or not any(
                isinstance(item, dict) and item.get("page") == page for item in old_pages):
            raise ValueError("A página não existe no manifesto anterior.")
        record["pages"] = [new_page if item.get("page") == page else item
                            for item in old_pages]
        record["regions"] = [row for row in record.get("regions", [])
                             if row.get("page") != page]
        record["regions"].extend(row for row in fresh.get("regions", [])
                                 if row.get("page") == page)
        record.update({"latest_reexecution_id": run_id, "updated_at": created_at,
                       "check_sha256": fresh["check_sha256"]})
        (staged / "solid-white-manifest.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if _sha(check_manifest_path(manga, chapter)) != check_hash:
            raise ValueError("Check mudou antes da publicação da reexecução.")
        current_source = source_for(manga, chapter, page)
        if _sha(current_source) != new_page.get("source_sha256"):
            raise ValueError("Imagem de entrada mudou antes da publicação da reexecução.")
        _promote(staged, target)
    return {"chapter": record["chapter"], "page": page, "run_id": run_id,
            "regions": len([row for row in fresh.get("regions", [])
                            if row.get("page") == page]), "status": "reexecuted"}


def _write_unchanged_page(manga, document, chapter, page, check_hash, target):
    if check_hash is None:
        raise ValueError("Check atual indisponível para reexecução.")
    source = source_for(manga, chapter, page)
    source_hash = _sha(source)
    with Image.open(source) as image:
        result = image.convert("RGB")
    if result.width * result.height > 100_000_000:
        raise ValueError("Imagem excede limite operacional")
    run_id = uuid4().hex
    created_at = datetime.now(timezone.utc).isoformat()
    (target / "clean").mkdir(parents=True)
    (target / "mask").mkdir()
    clean = target / "clean" / (Path(page).stem + "_clean.png")
    mask = target / "mask" / (Path(page).stem + "_mask.png")
    result.save(clean)
    Image.new("L", result.size, 0).save(mask)
    if (_sha(source) != source_hash or _sha(check_manifest_path(manga, chapter)) != check_hash):
        raise ValueError("Fonte ou Check alterados durante a reexecução.")
    page_record = {"page": page, "run_id": run_id, "created_at": created_at,
        "decision_sha256": decision_sha256([]), "check_sha256": check_hash,
        "source_sha256": source_hash, "result_sha256": _sha(clean),
        "mask_sha256": _sha(mask)}
    manifest = {"schema": "textoff_solid_stage_v1", "provider": document["provider"],
        "manga": document["obra"], "chapter": chapter, "run_id": run_id,
        "created_at": created_at, "motor": "laboratorio_solidos._filter",
        "check_sha256": check_hash, "preview_only": True,
        "pages": [page_record], "regions": []}
    (target / "solid-white-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _promote(staged, target):
    backup = target.parent / f".{target.name}.solid-backup-{uuid4().hex}"
    os.replace(target, backup)
    try:
        os.replace(staged, target)
    except Exception:
        if backup.exists() and not target.exists():
            os.replace(backup, target)
        raise
    shutil.rmtree(backup, ignore_errors=True)
