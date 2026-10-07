"""Run the dedicated transparent-balloon refinement stage."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

from processamento.unificacao_imagens import image_stitcher as v3
from .artifact_migration import mirror_stage_chapter
from .artifact_paths import artifact_ref
from .manifests import _stage_manifest, _stage_manifest_sha256
from .level2_manual_protection import load_level1_protection
from .query import query_merged_level2
from .runtime import REPOSITORY_ROOT, python_for
from .stages import LEVEL1, LEVEL2, stage_chapter
from .level2_validation import (
    build_output_manifest,
    promote_stage as _promote_stage,
    validate_level2_selection,
    validated_candidate_pages as _validated_candidate_pages,
)

def execute_merged_level2(manga: Path, chapters: list[str], progress, preflight=None,
                          *, provider: str, manga_name: str,
                          reprocess: bool = False) -> list[dict]:
    """Detect/inpaint text only within transparent-balloon masks preserved by Level I."""
    validate_level2_selection(manga, chapters, reprocess=reprocess)
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
        level1_dir = stage_chapter(manga, LEVEL1, name)
        chapter_row = next(row for row in query_merged_level2(manga)["chapters"]
                           if row["chapter"] == name)
        candidate_names = set(chapter_row.get("level2_candidate_pages", []))
        target = stage_chapter(manga, LEVEL2, name, read_legacy=False)
        target.parent.mkdir(parents=True, exist_ok=True)
        if batch_work is None:
            batch_work = Path(tempfile.mkdtemp(prefix=".textoff-level2-batch-", dir=target.parent))
        work = batch_work / name
        work.mkdir()
        staged = work / "staged"
        staged.mkdir()
        report_file = staged / artifact_ref("json", "level2-transparent-report.json")
        jobs.append({"chapter": name, "source_dir": str(source_dir), "level1_dir": str(level1_dir),
                     "output_dir": str(staged), "report": str(report_file),
                     "candidate_pages": sorted(candidate_names),
                     "protected_occurrences": load_level1_protection(
                         manga, provider, manga_name, name)})
        records.append((name, source_dir, target, staged, candidate_names))
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
        for name, source_dir, target, staged, candidate_names in records:
            report_file = staged / artifact_ref("json", "level2-transparent-report.json")
            if not report_file.is_file():
                raise RuntimeError(f"Nível II não gerou relatório para Cap. {name}.")
            report = json.loads(report_file.read_text(encoding="utf-8"))
            images = v3.merge_artifact_files(source_dir)
            level1_manifest = _stage_manifest(manga, LEVEL1, name)
            if (report.get("merge_pages_total", report.get("pages_analyzed")) != len(images)
                    or report.get("integrity_ok") is not True
                    or report.get("pages_analyzed") != len(candidate_names)):
                raise RuntimeError(f"Relatório Nível II incompleto ou inválido para Cap. {name}.")
            pages = _validated_candidate_pages(report, candidate_names, staged, level1_dir)
            report["report_reference"] = artifact_ref("json", report_file.name)
            output_manifest, clean_names = build_output_manifest(
                report, pages, images, candidate_names, level1_manifest,
                _stage_manifest_sha256(manga, LEVEL1, name))
            (staged / artifact_ref("json", "clean-manifest.json")).write_text(
                json.dumps(output_manifest, indent=2, ensure_ascii=False), encoding="utf-8")
            transparent_pages = [
                page["source"] for page in report.get("pages", [])
                if isinstance(page, dict) and page.get("transparent_balloons")
            ]
            prepared.append((name, target, staged, report, len(images), clean_names,
                             transparent_pages, len(pages)))
        for name, target, staged, report, image_count, clean_names, transparent_pages, analyzed_count in prepared:
            _promote_stage(staged, target)
            mirror_stage_chapter(manga, "auto_cleaner_transparencia_basica", name)
            from .consolidated import rebuild_consolidated
            consolidated = rebuild_consolidated(manga, name)
            from .final_consolidated import rebuild_final_baseline
            consolidated_final = rebuild_final_baseline(manga, name)
            outcome = report.get("outcome")
            results.append({"chapter": name, "status": "ok" if outcome == "visual_changes" else "no_change",
                            "outcome": outcome, "pages": image_count,
                            "outputs": len(clean_names), "masks": analyzed_count,
                            "analyzed_pages": analyzed_count,
                            "unchanged_pages": analyzed_count - len(clean_names),
                            "transparent_page_count": len(transparent_pages),
                            "transparent_pages": transparent_pages,
                            "text_pages": report.get("pages_with_text", 0),
                            "changed_pixels": report.get("changed_pixels", 0),
                            "consolidated": consolidated,
                            "consolidated_final": consolidated_final})
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
        message = (f"Cap. {name}: falha no Nível II: {item.get('error', 'resultado inválido')}"
                   if item.get("status") == "failed" else
                   f"Cap. {name}: sem pixels alterados; revisão concluída."
                   if item.get("status") == "no_change" else
                   f"Cap. {name}: Nível II finalizado.")
        progress(name, {"stage": "done", "percent": round(index * 100 / len(chapters)),
                        "completed": index, "total": len(chapters),
                        "message": message})
    return results
