"""Execute the isolated Merged Level I stage without the legacy refinement."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import time
import uuid

from processamento.limpeza_baloes.cleaner_v2.launcher import MODULE_DIR
from processamento.limpeza_baloes.cleaner_v2.ocr_manifest import ocr_manifest_metadata

from central_v2.backend.operational_log import emit
from .cleaner_process import run_balloon_authorization, run_panel_cleaner
from .artifact_paths import artifact_ref, prepare_artifact_dirs

ALGORITHM = "cleaner_v2_panel_cleaner_2_11_11"
PROFILE_NAME = "outlined-text.ini"


def clean_level1_chapter(images, target, *, source_stage, progress_job, chapter_name,
                         diagnostics=False, provider=None, manga_name=None):
    started = time.perf_counter()
    images = _validate_images(images)
    target = Path(target).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix=f".{target.name}.textoff-v2-", dir=target.parent))
    staged = work / "staged"
    staged.mkdir()
    try:
        input_dir, output_dir, clean_files, mask_files = run_panel_cleaner(
            images, work, progress_job, chapter_name,
        )
        diagnostic_pages = None
        execution_id = None
        if diagnostics:
            execution_id = uuid.uuid4().hex
            try:
                diagnostic_pages = _capture_raw_masks(
                    images, mask_files, staged / "diagnostics" / "raw_mask",
                    chapter_name=chapter_name,
                )
            except Exception as exc:
                diagnostic_pages = {
                    image.name: {"available": False, "error": str(exc)} for image in images
                }
                _log_diagnostic_error("falha ao capturar raw masks diagnósticas", {
                    "capítulo": chapter_name, "execution_id": execution_id, "erro": str(exc),
                })
        raw_masks = _preserve_raw_masks(mask_files, work / "raw_masks")
        report_path = work / "level1-balloon-report.json"
        report = run_balloon_authorization(
            images, output_dir, raw_masks, report_path, work,
            progress_job=progress_job, chapter_name=chapter_name,
        )
        if int(report.get("pages_total") or 0) != len(images):
            raise RuntimeError("Nível I não analisou todas as imagens do capítulo.")
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        level2_report = _level2_not_run(len(images))
        (output_dir / "level2-report.json").write_text(
            json.dumps(level2_report, indent=2, ensure_ascii=False), encoding="utf-8",
        )
        _stage_artifacts(output_dir, report_path, staged)
        manifest = _manifest(images, clean_files, mask_files, source_stage, report)
        manifest["execution"] = {
            "duration_seconds": round(time.perf_counter() - started, 3),
            "duration_scope": "chapter_total_including_validation_and_promotion",
        }
        official_manifest = staged / artifact_ref("json", "clean-manifest.json")
        official_manifest.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8",
        )
        if diagnostics:
            try:
                diagnostic_manifest = _diagnostics_manifest(
                    images, source_stage=source_stage, chapter_name=chapter_name,
                    provider=provider, manga_name=manga_name, report=report,
                    official_manifest=official_manifest, pages=diagnostic_pages,
                    execution_id=execution_id,
                )
                path = staged / "diagnostics" / "diagnostics-manifest.json"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(diagnostic_manifest, indent=2, ensure_ascii=False),
                                encoding="utf-8")
            except Exception as exc:
                _log_diagnostic_error("falha ao gravar manifesto diagnóstico da raw mask", {
                    "capítulo": chapter_name, "execution_id": execution_id,
                    "erro": str(exc),
                })
        _promote(staged, target)
        return _result(images, clean_files, mask_files, report, target)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _capture_raw_masks(images, mask_files, diagnostic_dir, *, chapter_name):
    """Byte-copy raw Cleaner masks and describe only copies verified on disk."""
    import cv2
    import numpy as np

    pages = {}
    try:
        diagnostic_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        for image in images:
            pages[image.name] = {"available": False, "error": str(exc)}
            _log_diagnostic_error("falha ao criar área de raw mask diagnóstica", {
                "capítulo": chapter_name, "página": image.name, "erro": str(exc),
            })
        return pages
    masks_by_name = {Path(mask).name: Path(mask) for mask in mask_files}
    for image in images:
        mask = masks_by_name.get(f"{image.stem}_mask.png")
        entry = {"available": False}
        destination = diagnostic_dir / f"{image.stem}_raw_mask.png"
        try:
            if mask is None or not mask.is_file():
                raise FileNotFoundError("raw mask PNG não encontrada para a página")
            source_image = cv2.imread(str(image), cv2.IMREAD_UNCHANGED)
            raw_mask = cv2.imread(str(mask), cv2.IMREAD_UNCHANGED)
            if source_image is None or raw_mask is None:
                raise ValueError("não foi possível ler a imagem fonte ou a raw mask")
            height, width = source_image.shape[:2]
            if raw_mask.shape[:2] != (height, width):
                raise ValueError("dimensões da raw mask diferem da imagem fonte")
            if raw_mask.ndim == 2:
                active_pixels = int(np.count_nonzero(raw_mask))
            elif raw_mask.ndim == 3:
                active_pixels = int(np.count_nonzero(np.any(raw_mask != 0, axis=2)))
            else:
                raise ValueError("formato de raw mask não suportado")

            shutil.copy2(mask, destination)
            source_sha256 = _sha256(mask)
            copied_sha256 = _sha256(destination)
            if copied_sha256 != source_sha256:
                raise OSError("SHA-256 da cópia difere da raw mask produzida")
            entry = {
                "available": True,
                "file": f"raw_mask/{destination.name}",
                "sha256": copied_sha256,
                "width": width,
                "height": height,
                "mask_pixels": active_pixels,
            }
        except (OSError, ValueError, TypeError) as exc:
            try:
                destination.unlink(missing_ok=True)
            except OSError as cleanup_error:
                entry["cleanup_error"] = str(cleanup_error)
            entry["error"] = str(exc)
            _log_diagnostic_error("falha ao preservar raw mask diagnóstica", {
                "capítulo": chapter_name, "página": image.name, "erro": str(exc),
            })
        pages[image.name] = entry
    return pages


def _diagnostics_manifest(images, *, source_stage, chapter_name, provider, manga_name,
                          report, official_manifest, pages, execution_id):
    source_manifest = images[0].parent / "merge-manifest.json" if images else None
    return {
        "schema": "textoff_level1_diagnostics_v1",
        "execution_id": execution_id,
        "provider": provider,
        "manga": manga_name,
        "chapter": str(chapter_name),
        "source": {
            "stage": str(source_stage).upper(),
            "manifest_sha256": _sha256(source_manifest) if source_manifest and source_manifest.is_file() else None,
            "pages": [image.name for image in images],
        },
        "level1": {
            "algorithm": ALGORITHM,
            "authorization_algorithm": report.get("algorithm"),
            "official_manifest_sha256": _sha256(official_manifest),
        },
        "diagnostics": {
            "raw_mask": {"enabled": True, "pages": pages},
        },
    }


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _log_diagnostic_error(message, fields):
    try:
        emit("ERROR", message, **fields)
    except Exception:
        # Diagnostic logging must not change the operational Cleaner outcome.
        pass


def _validate_images(images):
    paths = [Path(image).resolve() for image in images]
    if not paths or any(not path.is_file() for path in paths):
        raise ValueError("Nível I requer imagens MERGE existentes.")
    names = [path.name for path in paths]
    if len(names) != len(set(names)):
        raise ValueError("O lote contém nomes de imagem duplicados.")
    return paths


def _preserve_raw_masks(mask_files, folder):
    folder.mkdir()
    paths = []
    for mask in mask_files:
        copy = folder / mask.name
        shutil.copy2(mask, copy)
        paths.append(copy)
    return paths


def _stage_artifacts(output_dir, report_path, staged):
    prepare_artifact_dirs(staged)
    for artifact in output_dir.iterdir():
        if artifact.is_file():
            name = artifact.name
            if "_clean." in name:
                kind = "clean"
            elif any(token in name for token in ("_mask.", "_transparent_balloons.", "_deferred_text.")):
                kind = "mask"
            elif artifact.suffix.lower() == ".json":
                kind = "json"
            else:
                raise RuntimeError(f"Tipo de artefato Nível I não reconhecido: {name}.")
            shutil.copy2(artifact, staged / kind / name)
    shutil.copy2(report_path, staged / artifact_ref("json", report_path.name))


def _level2_not_run(pages):
    return {
        "algorithm": None, "pages_analyzed": pages, "pages_level2": 0,
        "components_level2": 0, "status": "not_run", "reason": "explicit_level1_execution",
    }


def _manifest(images, clean_files, mask_files, source_stage, report):
    pages = report.get("pages", [])
    deferred = sum(int(page.get("transparent_components_deferred") or 0) for page in pages)
    return {
        "schema_version": 3, "algorithm": ALGORITHM,
        "engine": "Panel Cleaner", "engine_version": "2.11.11",
        "profile": PROFILE_NAME, "offline": True,
        "ocr": ocr_manifest_metadata(MODULE_DIR / PROFILE_NAME),
        "source_stage": str(source_stage).upper(), "source_immutable": True,
        "pages_total": len(images), "outputs_total": len(clean_files),
        "masks_total": len(mask_files), "mask_complete": True, "integrity_ok": True,
        "source_artifacts": [image.name for image in images],
        "clean_artifacts": [artifact_ref("clean", path.name) for path in clean_files],
        "mask_artifacts": [artifact_ref("mask", path.name) for path in mask_files],
        "authorization": {},
        "level1": _level1_manifest(report, pages, deferred),
        "level2": {**_level2_not_run(len(images)),
                    "report": artifact_ref("json", "level2-report.json")},
        "failures": [],
    }


def _level1_manifest(report, pages, deferred):
    return {
        "algorithm": report.get("algorithm"), "policy": report.get("policy"),
        "fail_closed": report.get("fail_closed"), "model": report.get("model"),
        "pages_total": report.get("pages_total"),
        "cleaner_mask_pixels": report.get("cleaner_mask_pixels"),
        "authorized_mask_pixels": report.get("authorized_mask_pixels"),
        "authorized_percent": report.get("authorized_percent"),
        "transparent_balloons_total": sum(len(page.get("transparent_balloons", [])) for page in pages),
        "transparent_components_deferred": deferred,
        "transparent_mask_artifacts": [page["transparent_mask_artifact"] for page in pages],
        "deferred_text_mask_artifacts": [
            page["deferred_text_mask_artifact"] for page in pages
            if page.get("deferred_text_mask_artifact")
        ],
        "report": artifact_ref("json", "level1-balloon-report.json"),
    }


def _promote(staged, target):
    backup = target.parent / f".{target.name}.backup-textoff-v2-{uuid.uuid4().hex}"
    had_previous = target.exists()
    try:
        if had_previous:
            os.replace(target, backup)
        os.replace(staged, target)
    except Exception:
        if had_previous and backup.exists() and not target.exists():
            os.replace(backup, target)
        raise
    else:
        if backup.exists():
            shutil.rmtree(backup)


def _result(images, clean_files, mask_files, report, target):
    pages = report.get("pages", [])
    pending = [page["source"] for page in pages if page.get("transparent_components_deferred")]
    return {
        "status": "ok", "pages": len(images), "outputs": len(clean_files),
        "masks": len(mask_files), "mask_complete": True,
        "level2_pages": 0, "level2_components": 0,
        "transparent_balloons": sum(len(page.get("transparent_balloons", [])) for page in pages),
        "level2_pending_pages": pending, "stage_folder": str(target),
    }
