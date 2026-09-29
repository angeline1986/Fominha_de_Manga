"""Execute the isolated Merged Level I stage without the legacy refinement."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import tempfile
import time
import uuid

from processamento.limpeza_baloes.cleaner_v2.launcher import MODULE_DIR
from processamento.limpeza_baloes.cleaner_v2.ocr_manifest import ocr_manifest_metadata

from .cleaner_process import run_balloon_authorization, run_panel_cleaner

ALGORITHM = "cleaner_v2_panel_cleaner_2_11_11"
PROFILE_NAME = "outlined-text.ini"


def clean_level1_chapter(images, target, *, source_stage, progress_job, chapter_name):
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
        (staged / "clean-manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8",
        )
        _promote(staged, target)
        return _result(images, clean_files, mask_files, report, target)
    finally:
        shutil.rmtree(work, ignore_errors=True)


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
    for artifact in output_dir.iterdir():
        if artifact.is_file():
            shutil.copy2(artifact, staged / artifact.name)
    shutil.copy2(report_path, staged / report_path.name)


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
        "clean_artifacts": [path.name for path in clean_files],
        "mask_artifacts": [path.name for path in mask_files],
        "authorization": {},
        "level1": _level1_manifest(report, pages, deferred),
        "level2": {**_level2_not_run(len(images)), "report": "level2-report.json"},
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
        "report": "level1-balloon-report.json",
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
