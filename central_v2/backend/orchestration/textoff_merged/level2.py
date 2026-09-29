"""Run the dedicated transparent-balloon refinement stage."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import uuid

from processamento.unificacao_imagens import image_stitcher as v3
from .artifact_paths import artifact_file, artifact_ref
from .execution import validate_selection
from .manifests import _stage_manifest, _stage_manifest_sha256
from .level2_vision import ALGORITHM, AUTHORIZED_DILATION, BASE_DILATION, LAMA_PADDING, REFERENCE_RECIPE
from .query import query_merged_level2
from .runtime import REPOSITORY_ROOT, python_for

def validate_level2_selection(manga: Path, chapters: object) -> list[str]:
    selected = validate_selection(manga, chapters)
    rows = {row["chapter"]: row for row in query_merged_level2(manga)["chapters"]}
    for name in selected:
        row = rows.get(name)
        if not row or row["level2_status"] != "pending" or not row["selectable"]:
            raise ValueError(f"Capítulo {name} não possui balões transparentes pendentes do Nível I.")
    return selected


def _promote_stage(staged: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    backup = target.parent / f".{target.name}.backup-level2-{uuid.uuid4().hex}"
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


def execute_merged_level2(manga: Path, chapters: list[str], progress, preflight=None) -> list[dict]:
    """Detect/inpaint text only within transparent-balloon masks preserved by Level I."""
    validate_level2_selection(manga, chapters)
    runner = Path(__file__).resolve().parent / "level2_transparent.py"
    level2_python = python_for("merged_nivel_ii")
    if not runner.is_file():
        raise RuntimeError("Executável do TextOff Merged Nível II não foi encontrado na Central V2.")

    results = []
    jobs, records = [], []
    batch_work = None
    for name in chapters:
        if preflight:
            preflight()
        chapter = manga / "IMG" / name
        if not v3.is_chapter_merged(chapter):
            results.append({"chapter": name, "status": "failed", "error": "MERGE oficial alterado antes do Nível II."})
            continue
        source_dir = v3.merge_output_dir(chapter)
        level1_dir = manga / "FLUXO_SECUNDARIO" / "04_TEXTO_OFF" / "MERGED_NIVEL_I" / name
        target = manga / "FLUXO_SECUNDARIO" / "04_TEXTO_OFF" / "MERGED_NIVEL_II" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if batch_work is None:
            batch_work = Path(tempfile.mkdtemp(prefix=".textoff-level2-batch-", dir=target.parent))
        work = batch_work / name
        work.mkdir()
        staged = work / "staged"
        staged.mkdir()
        report_file = staged / artifact_ref("json", "level2-transparent-report.json")
        jobs.append({"chapter": name, "source_dir": str(source_dir), "level1_dir": str(level1_dir),
                     "output_dir": str(staged), "report": str(report_file)})
        records.append((name, source_dir, target, staged))
    if not jobs:
        return results

    progress_file, batch_manifest = batch_work / "progress.json", batch_work / "jobs.json"
    batch_manifest.write_text(json.dumps(jobs, ensure_ascii=False), encoding="utf-8")
    command = [str(level2_python), "-m", "central_v2.backend.orchestration.textoff_merged.level2_transparent",
               "--batch-manifest", str(batch_manifest), "--progress", str(progress_file)]
    for name, *_ in records:
        progress(name, {"stage": "level2", "percent": 0, "completed": 0,
                        "total": len(records), "message": "Iniciando detector e reconstrutor do Nível II."})
    process = subprocess.Popen(command, cwd=REPOSITORY_ROOT)
    last_progress, started = None, time.monotonic()
    try:
        while process.poll() is None:
            if time.monotonic() - started > 1800:
                process.kill()
                raise RuntimeError("Nível II excedeu 30 minutos; Nível I e Legado foram preservados.")
            if progress_file.is_file():
                try:
                    payload = json.loads(progress_file.read_text(encoding="utf-8"))
                    if payload != last_progress:
                        last_progress = payload
                        for name, *_ in records:
                            progress(name, {"stage": "level2", "percent": int(payload.get("percent", 0)),
                                            "completed": int(payload.get("completed", 0)),
                                            "total": len(records),
                                            "message": payload.get("detail", "Nível II em execução")})
                except (OSError, ValueError, TypeError):
                    pass
            time.sleep(0.25)
        if process.returncode != 0:
            raise RuntimeError(f"Nível II encerrou sem resultado validado (código {process.returncode}).")

        prepared = []
        for name, source_dir, target, staged in records:
            report_file = staged / artifact_ref("json", "level2-transparent-report.json")
            if not report_file.is_file():
                raise RuntimeError(f"Nível II não gerou relatório para Cap. {name}.")
            report = json.loads(report_file.read_text(encoding="utf-8"))
            images = v3.merge_artifact_files(source_dir)
            level1_manifest = _stage_manifest(manga, "MERGED_NIVEL_I", name)
            if report.get("pages_analyzed") != len(images) or report.get("integrity_ok") is not True:
                raise RuntimeError(f"Relatório Nível II incompleto ou inválido para Cap. {name}.")
            clean_names = [item["clean"] for item in report.get("pages", [])]
            if len(clean_names) != len(images) or any(
                artifact_file(staged, filename, "clean") is None for filename in clean_names
            ):
                raise RuntimeError(f"Nível II não gerou todas as imagens finais do Cap. {name}.")
            output_manifest = {
                "schema_version": 1, "algorithm": ALGORITHM,
                "source_stage": "MERGED_NIVEL_I", "integrity_ok": True,
                "source_artifacts": [path.name for path in images],
                "source_level1_artifacts": level1_manifest.get("clean_artifacts", []),
                "source_level1_manifest_sha256": _stage_manifest_sha256(
                    manga, "MERGED_NIVEL_I", name
                ),
                "clean_artifacts": clean_names, "outputs_total": len(clean_names),
                "mask_artifacts": [item["mask"] for item in report["pages"]],
                "recipe": {"reference": REFERENCE_RECIPE, "base_dilation": BASE_DILATION,
                           "authorized_dilation": AUTHORIZED_DILATION, "lama_padding": LAMA_PADDING},
                "pages_with_text": report.get("pages_with_text", 0),
                "mask_pixels": report.get("mask_pixels", 0),
                "changed_pixels": report.get("changed_pixels", 0),
                "outcome": report.get("outcome"),
                "report": artifact_ref("json", report_file.name),
                "execution": {
                    "duration_seconds": report.get("duration_seconds"),
                    "duration_scope": "chapter_total_including_mask_creation_inpainting_and_validation",
                },
            }
            (staged / artifact_ref("json", "clean-manifest.json")).write_text(
                json.dumps(output_manifest, indent=2, ensure_ascii=False), encoding="utf-8")
            transparent_pages = [
                page["source"] for page in report.get("pages", [])
                if isinstance(page, dict) and page.get("transparent_balloons")
            ]
            prepared.append((name, target, staged, report, len(images), clean_names, transparent_pages))
        for name, target, staged, report, image_count, clean_names, transparent_pages in prepared:
            _promote_stage(staged, target)
            outcome = report.get("outcome")
            results.append({"chapter": name, "status": "ok" if outcome == "visual_changes" else "no_change",
                            "outcome": outcome, "pages": image_count,
                            "outputs": len(clean_names), "masks": len(report["pages"]),
                            "transparent_page_count": len(transparent_pages),
                            "transparent_pages": transparent_pages,
                            "text_pages": report.get("pages_with_text", 0),
                            "changed_pixels": report.get("changed_pixels", 0)})
    except Exception as exc:
        if process.poll() is None:
            process.kill()
        for name, *_ in records:
            if not any(item.get("chapter") == name for item in results):
                results.append({"chapter": name, "status": "failed", "error": str(exc)})
    finally:
        shutil.rmtree(batch_work, ignore_errors=True)
    result_by_chapter = {item["chapter"]: item for item in results}
    for index, name in enumerate(chapters, 1):
        item = result_by_chapter.get(name, {})
        message = (f"Cap. {name}: sem pixels alterados; revisar máscaras e resultado."
                   if item.get("status") == "no_change" else f"Cap. {name}: Nível II finalizado.")
        progress(name, {"stage": "done", "percent": round(index * 100 / len(chapters)),
                        "completed": index, "total": len(chapters),
                        "message": message})
    return results
