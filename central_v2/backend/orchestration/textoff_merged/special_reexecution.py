"""Prepare a confirmed special-treatment reexecution from current Check data."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import tempfile
from uuid import uuid4

from central_v2.backend.orchestration.textoff_special.artifacts import sha256

from .artifact_paths import artifact_ref
from .auto_cleaner_check_manifest import manifest_path as check_manifest_path
from .level2_validation import promote_stage
from .special_treatments_manifest import manifest_path, rebuild_special_treatments
from .stages import stage_chapter

STAGES = {
    "degrade": ("PINCEL_DEGRADE", "degrade-manifest.json"),
    "gradiente_suave": ("PINCEL_SUAVE", "suave-manifest.json"),
}


def validate_reexecution(manga: Path, provider: str, chapters: object,
                         treatment: str) -> list[str]:
    if (not isinstance(chapters, list) or not chapters
            or any(not isinstance(name, str) or not name or Path(name).name != name
                   or name in {".", ".."} or "\\" in name for name in chapters)
            or len(set(chapters)) != len(chapters)):
        raise ValueError("Selecione capítulos válidos sem repetição.")
    for chapter in chapters:
        path = manifest_path(manga, chapter)
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows = (payload.get("treatments") or {}).get(treatment)
        if (payload.get("provider") != provider or payload.get("manga") != manga.name
                or not isinstance(rows, list)
                or not any(isinstance(row, dict) and row.get("status") in {"processed", "no_change"}
                           for row in rows)):
            raise ValueError(f"Capítulo {chapter} não possui resultado anterior para reexecutar.")
        _current_check(manga, provider, chapter)
    return chapters


def prepare_reexecution(manga: Path, provider: str, chapter: str,
                        treatment: str) -> dict:
    special_path = manifest_path(manga, chapter)
    previous_bytes = special_path.read_bytes()
    previous = json.loads(previous_bytes.decode("utf-8"))
    old_rows = (previous.get("treatments") or {}).get(treatment)
    if not isinstance(old_rows, list) or not any(
            isinstance(row, dict) and row.get("status") in {"processed", "no_change"}
            for row in old_rows):
        raise ValueError("Não há resultado anterior elegível para reexecução.")
    check_path, check_hash = _current_check(manga, provider, chapter)
    document = {"provider": provider, "obra": manga.name, "capitulo": chapter}
    stage_target = _stage_path(manga, chapter, treatment)
    with tempfile.TemporaryDirectory(prefix=".reexecute-rollback-", dir=special_path.parent,
                                     ignore_cleanup_errors=True) as work:
        stage_existed = stage_target.is_dir()
        stage_backup = Path(work) / "stage-before"
        if stage_existed:
            shutil.copytree(stage_target, stage_backup)
        try:
            path, fresh, _changed = rebuild_special_treatments(manga, document, chapter)
            if path != special_path or sha256(check_path) != check_hash:
                raise ValueError("O Check mudou durante a preparação da reexecução.")
            run_id = uuid4().hex
            history = list(previous.get("reexecution_history", []))
            history.append({
                "id": run_id, "treatment": treatment,
                "started_at": datetime.now(timezone.utc).isoformat(),
                "previous_check_sha256": (previous.get("source_check") or {}).get("sha256"),
                "current_check_sha256": check_hash,
                "superseded_occurrences": [
                    {key: row[key] for key in ("id", "page", "status", "box_pixels", "result") if key in row}
                    for row in old_rows if isinstance(row, dict)
                ],
            })
            for row in (fresh.get("treatments") or {}).get(treatment, []):
                row["status"] = "pending"
                row.pop("result", None)
                row.pop("error", None)
            fresh["reexecution_history"] = history
            from .auto_cleaner_check_manifest import _write_atomic
            _write_atomic(special_path, fresh)
            _archive_stage(manga, chapter, treatment, run_id, check_hash)
            if sha256(check_path) != check_hash:
                raise ValueError("O Check mudou durante a preparação da reexecução.")
        except Exception as failure:
            rollback_errors = []
            for restore in (
                lambda: _restore_special(special_path, previous_bytes),
                lambda: _restore_stage(stage_target, stage_backup, stage_existed),
            ):
                try:
                    restore()
                except Exception as rollback_error:
                    rollback_errors.append(rollback_error)
            if rollback_errors:
                raise RuntimeError("Falha ao restaurar o estado anterior da reexecução.") from failure
            raise
    return {"id": run_id, "path": special_path, "hash": sha256(special_path)}


def _current_check(manga, provider, chapter):
    path = check_manifest_path(manga, chapter)
    if not path.is_file():
        raise ValueError("Check atual indisponível para reexecução.")
    from .auto_cleaner_check_manifest import _read_check_manifest
    _read_check_manifest(path, {"provider": provider, "obra": manga.name, "capitulo": chapter})
    return path, sha256(path)


def _archive_stage(manga, chapter, treatment, run_id, check_hash):
    _stage_name, filename = STAGES[treatment]
    target = _stage_path(manga, chapter, treatment)
    if not target.is_relative_to(manga.resolve()) or not target.is_dir():
        return
    with tempfile.TemporaryDirectory(prefix=".special-reexecute-", dir=target.parent) as work:
        staged = Path(work) / "stage"
        shutil.copytree(target, staged)
        ref = artifact_ref("json", filename)
        manifest = staged / ref
        if not manifest.is_file():
            raise ValueError("Manifesto operacional anterior ausente para arquivamento.")
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        pages = payload.get("pages")
        if not isinstance(pages, dict):
            raise ValueError("Manifesto operacional incompatível para arquivamento.")
        replaced = []
        for page, record in pages.items():
            archived = []
            for key in ("output", "report"):
                artifact = (record.get(key) or {}).get("artifact")
                if not artifact:
                    continue
                source = (staged / artifact).resolve()
                if not source.is_relative_to(staged.resolve()) or not source.is_file():
                    raise ValueError("Artefato anterior inválido para arquivamento.")
                digest = sha256(source)
                if digest != (record.get(key) or {}).get("sha256"):
                    raise ValueError("Hash do resultado anterior divergente.")
                archive_ref = f"archive/{run_id}/{artifact}"
                destination = staged / archive_ref
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, destination)
                archived.append({"artifact": archive_ref, "sha256": digest})
                source.unlink()
            replaced.append({"page": page, "record": record, "archived_artifacts": archived})
        payload.setdefault("superseded_results", []).append({
            "id": run_id, "treatment": treatment, "check_sha256": check_hash,
            "superseded_at": datetime.now(timezone.utc).isoformat(), "pages": replaced,
        })
        payload["pages"] = {}
        manifest.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        promote_stage(staged, target)


def _stage_path(manga, chapter, treatment):
    stage_name, _filename = STAGES[treatment]
    target = stage_chapter(manga, stage_name, chapter, read_legacy=False).resolve()
    if not target.is_relative_to(Path(manga).resolve()):
        raise ValueError("Destino do resultado anterior fora da obra.")
    return target


def _restore_special(path, original):
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.rollback-", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(original)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _restore_stage(target, backup, existed):
    if existed:
        with tempfile.TemporaryDirectory(prefix=".stage-restore-", dir=target.parent) as work:
            restored = Path(work) / "stage"
            shutil.copytree(backup, restored)
            promote_stage(restored, target)
    elif target.exists():
        shutil.rmtree(target)
