"""Run and validate the existing Panel Cleaner executable for a chapter."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import time

from processamento.limpeza_baloes.cleaner_v2.launcher import MODULE_DIR
from .runtime import REPOSITORY_ROOT, python_for
from central_v2.backend.operational_log import emit, short_duration
from .cleaner_logging import consume_messages, start_stream_readers

PANEL_CLEANER_PROGRESS_MAX = 0.9


def run_panel_cleaner(images, work: Path, progress_job=None, chapter_name=None):
    input_dir, output_dir = work / "input", work / "output"
    input_dir.mkdir()
    output_dir.mkdir()
    for source in images:
        (input_dir / source.name).symlink_to(source)

    progress_file = work / "progress.json"
    command = panel_cleaner_command(input_dir, output_dir, progress_file, chapter_name)
    process = subprocess.Popen(command, cwd=MODULE_DIR, text=True, encoding="utf-8",
                               errors="replace", stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               bufsize=1)
    messages, readers = start_stream_readers(process)
    stdout_tail, stderr_tail = [], []
    last_stamp, started = None, time.monotonic()
    try:
        while process.poll() is None:
            if time.monotonic() - started > 900:
                process.kill()
                for reader in readers:
                    reader.join(timeout=2)
                consume_messages(messages, stdout_tail, stderr_tail)
                diagnostic = "\n".join(("\n".join(stdout_tail), "\n".join(stderr_tail))).strip()
                raise RuntimeError("Cleaner V2 excedeu 900 segundos; "
                                   f"a saída anterior foi preservada. {diagnostic[-4000:]}")
            _report_progress(progress_file, progress_job, chapter_name, last_stamp)
            consume_messages(messages, stdout_tail, stderr_tail)
            if progress_file.is_file():
                try:
                    last_stamp = json.loads(progress_file.read_text(encoding="utf-8")).get("updated_at")
                except (OSError, ValueError, TypeError):
                    pass
            time.sleep(0.25)
    except Exception:
        if process.poll() is None:
            process.kill()
        raise
    for reader in readers:
        reader.join(timeout=2)
    consume_messages(messages, stdout_tail, stderr_tail)
    if process.returncode != 0:
        diagnostic = "\n".join(("\n".join(stdout_tail), "\n".join(stderr_tail))).strip()
        raise RuntimeError(f"Cleaner V2 encerrou com código {process.returncode}. {diagnostic[-4000:]}")
    if progress_job is not None:
        prefix = f"Cap. {chapter_name}: " if chapter_name else ""
        progress_job.progress_detail = prefix + "Cleaner V2 concluído"
        progress_job.message = progress_job.progress_detail

    cleans = [_single_output(output_dir, image.stem, "clean") for image in images]
    masks = [_single_output(output_dir, image.stem, "mask") for image in images]
    if any(item is None for item in cleans) or any(item is None for item in masks):
        raise RuntimeError("Cleaner V2 não gerou clean e mask para todas as imagens do capítulo.")
    return input_dir, output_dir, cleans, masks


def panel_cleaner_command(input_dir: Path, output_dir: Path, progress_file: Path,
                          chapter_name=None) -> list[str]:
    command = [
        str(python_for("merged_nivel_i")), str(MODULE_DIR / "main.py"),
        "-i", str(input_dir.resolve()), "-o", str(output_dir.resolve()),
        "--profile", str(MODULE_DIR / "outlined-text.ini"), "--timeout", "900",
        "--offline", "--progress-file", str(progress_file.resolve()), "--central-mode",
    ]
    if chapter_name:
        command.extend(("--chapter-name", str(chapter_name)))
    return command


def run_balloon_authorization(images, output_dir, raw_masks, report_path, work,
                              progress_job=None, chapter_name=None):
    request_path, progress_path = work / "authorization-request.json", work / "authorization-progress.json"
    request_path.write_text(json.dumps({
        "images": [str(path.resolve()) for path in images],
        "output_dir": str(output_dir.resolve()), "raw_masks": [str(path.resolve()) for path in raw_masks],
        "report_path": str(report_path.resolve()), "progress_path": str(progress_path.resolve()),
        "chapter": str(chapter_name or ""),
    }), encoding="utf-8")
    command = [str(python_for("merged_nivel_i")), "-m",
               "central_v2.backend.orchestration.textoff_merged.level1_worker",
               "--request", str(request_path)]
    authorization_started = time.monotonic()
    if progress_job is not None:
        progress_job.progress_value = PANEL_CLEANER_PROGRESS_MAX
        prefix = f"Cap. {chapter_name}: " if chapter_name else ""
        progress_job.progress_detail = prefix + "validando balões do Nível I..."
        progress_job.message = progress_job.progress_detail
    emit("INFO", "validação de balões iniciada", **{
        "capítulo": chapter_name, "páginas": len(images),
    })
    process = subprocess.Popen(command, cwd=REPOSITORY_ROOT, text=True, encoding="utf-8",
                               errors="replace", stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               bufsize=1)
    messages, readers = start_stream_readers(process)
    stdout_tail, stderr_tail = [], []
    last_payload, started = None, time.monotonic()
    try:
        while process.poll() is None:
            if time.monotonic() - started > 1800:
                process.kill()
                raise RuntimeError("Autorização de balões do Nível I excedeu 30 minutos.")
            if progress_path.is_file():
                try:
                    payload = json.loads(progress_path.read_text(encoding="utf-8"))
                    if payload != last_payload and progress_job is not None:
                        last_payload = payload
                        prefix = f"Cap. {chapter_name}: " if chapter_name else ""
                        progress_job.progress_detail = prefix + payload.get("detail", "Validando balões...")
                        progress_job.message = progress_job.progress_detail
                except (OSError, ValueError, TypeError):
                    pass
            consume_messages(messages, stdout_tail, stderr_tail)
            time.sleep(0.25)
    except Exception:
        if process.poll() is None:
            process.kill()
        raise
    for reader in readers:
        reader.join(timeout=2)
    consume_messages(messages, stdout_tail, stderr_tail)
    if process.returncode != 0 or not report_path.is_file():
        diagnostic = "\n".join(("\n".join(stdout_tail), "\n".join(stderr_tail))).strip()
        emit("ERROR", "validação de balões falhou", **{
            "capítulo": chapter_name,
            "diagnóstico": diagnostic[-1000:],
        })
        raise RuntimeError(f"Autorização de balões do Nível I falhou (código {process.returncode}). {diagnostic[-4000:]}")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    emit("INFO", "validação de balões concluída", **{
        "capítulo": chapter_name, "páginas": report.get("pages_total"),
        "duração": short_duration(time.monotonic()-authorization_started),
    })
    return report


def _single_output(folder: Path, stem: str, kind: str) -> Path | None:
    matches = sorted(path for path in folder.glob(f"{stem}_{kind}.*") if path.is_file())
    if len(matches) > 1:
        raise RuntimeError(f"Cleaner V2 gerou máscaras duplicadas para {stem}.")
    return matches[0] if matches else None


def _report_progress(progress_file, progress_job, chapter_name, last_stamp):
    if progress_job is None or not progress_file.is_file():
        return
    try:
        payload = json.loads(progress_file.read_text(encoding="utf-8"))
        if payload.get("updated_at") == last_stamp:
            return
        ratio = max(0.0, min(1.0, float(payload.get("overall") or 0.0)))
        progress_job.progress_value = ratio * PANEL_CLEANER_PROGRESS_MAX
        prefix = f"Cap. {chapter_name}: " if chapter_name else ""
        progress_job.progress_detail = prefix + str(payload.get("detail") or "Cleaner V2 processando...")
        progress_job.message = progress_job.progress_detail
    except (OSError, ValueError, TypeError):
        return
