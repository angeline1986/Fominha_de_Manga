"""Coordinate Level I jobs while delegating all image decisions to V3."""
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import threading

from orquestracao.auto_merge.eventos_nivel1 import record_event
from processamento.unificacao_imagens import image_stitcher as v3
from processamento.unificacao_imagens.auto_merge.materializacao_nivel1 import materialize_safe_intervals
from processamento.unificacao_imagens.auto_merge.planejamento_nivel1 import plan_level1
from processamento.unificacao_imagens.auto_merge.promocao_nivel1 import promote_complete, write_stage_manifest


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_selection(manga: Path, chapters: object) -> list[str]:
    if not isinstance(chapters, list) or not chapters or len(chapters) > 100:
        raise ValueError("Selecione de 1 a 100 capítulos.")
    if any(not isinstance(name, str) or not name for name in chapters):
        raise ValueError("A seleção contém capítulo inválido.")
    if len(set(chapters)) != len(chapters):
        raise ValueError("A seleção contém capítulos repetidos.")
    img_root = (manga / "IMG").resolve()
    if not img_root.is_relative_to(manga.resolve()):
        raise ValueError("Diretório IMG fora da obra.")
    available = {path.name for path in img_root.iterdir() if path.is_dir() and v3.list_pages(path)}
    if any(name not in available for name in chapters):
        raise ValueError("A seleção contém capítulos fora da obra.")
    return chapters


def _run_chapter(manga: Path, chapter_name: str, job_id: str, progress) -> dict:
    chapter = manga / "IMG" / chapter_name
    if chapter.resolve().parent != (manga / "IMG").resolve():
        raise ValueError("Capítulo fora do diretório IMG.")
    record_event(manga, {"time": _timestamp(), "job_id": job_id, "chapter": chapter_name, "status": "started"})
    try:
        official = v3.merge_output_dir(chapter)
        if v3.is_chapter_merged(chapter):
            result = {"chapter": chapter_name, "status": "already_complete"}
            record_event(manga, {"time": _timestamp(), "job_id": job_id, **result})
            return result
        if official.exists():
            raise FileExistsError(f"{chapter_name}: destino oficial existente não reconhecido; nada foi alterado.")
        stage = manga / "FLUXO_SECUNDARIO" / "01_MERGE_PROCESSAMENTO" / "AUTO_MERGE" / chapter_name
        if stage.exists():
            raise FileExistsError(f"{chapter_name}: estágio existente; revisar antes de nova execução.")
        pages = v3.list_pages(chapter)
        if not pages:
            raise ValueError(f"{chapter_name}: nenhuma imagem ativa encontrada.")
        progress(chapter_name, {"stage": "prepare", "message": "Preparando análise das imagens"})
        infos, bands, total_height, _ = v3.analyze_chapter(
            pages, progress_callback=lambda item: progress(chapter_name, item),
        )
        progress(chapter_name, {"stage": "choose_cuts", "message": "Calculando cortes seguros"})
        plan = plan_level1(total_height, bands)
        progress(chapter_name, {"stage": "materialize", "message": "Gravando segmentos seguros"})
        artifacts = materialize_safe_intervals(plan, infos, stage)
        write_stage_manifest(chapter, plan, artifacts)
        if plan.status == "complete":
            progress(chapter_name, {"stage": "promote", "message": "Validando e promovendo MERGE"})
            promote_complete(chapter, plan, artifacts)
            status = "promoted"
        elif plan.status == "partial":
            status = "partial"
        else:
            status = "unresolved"
        pending = [item for item in plan.intervals if item.status == "pending"]
        reasons = sorted({item.reason for item in pending})
        result = {
            "chapter": chapter_name, "status": status, "artifacts": len(artifacts),
            "pending_segments": len(pending),
            "residuals": [{"global_start": item.start, "global_end": item.end} for item in pending],
            "reason_codes": reasons,
            "next_stage": "Auto-Merge Nível II" if pending else "—",
        }
        progress(chapter_name, {"stage": "done", "message": f"Capítulo finalizado: {status}"})
        record_event(manga, {"time": _timestamp(), "job_id": job_id, **result})
        return result
    except Exception as exc:
        progress(chapter_name, {"stage": "done", "message": "Capítulo finalizado com erro"})
        record_event(manga, {
            "time": _timestamp(), "job_id": job_id, "chapter": chapter_name,
            "status": "failed", "error": str(exc),
        })
        raise


def execute_level1(manga: Path, chapters: list[str], job_id: str, progress, preflight=None) -> list[dict]:
    validate_selection(manga, chapters)
    lock = threading.RLock()
    ratios = {chapter: 0.0 for chapter in chapters}
    finished = set()

    def report(chapter: str, event: dict) -> None:
        stage = event.get("stage")
        current = max(0, int(event.get("current") or 0))
        total = max(1, int(event.get("total") or 1))
        ratio = {
            "prepare": 0.01, "choose_cuts": 0.78, "materialize": 0.86,
            "promote": 0.97, "done": 1.0,
        }.get(stage, 0.05 + (0.70 * min(current / total, 1.0)) if stage == "analyze_pages" else 0.0)
        with lock:
            ratios[chapter] = max(ratios[chapter], ratio)
            value = sum(ratios.values())
            percent = round(value * 100 / len(chapters))
            progress(chapter, {
                **event, "completed": len(finished), "total": len(chapters),
                "value": value, "max": len(chapters), "percent": percent,
            })

    def process(index: int, chapter: str) -> dict:
        try:
            if preflight is not None:
                preflight()
        except Exception as exc:
            report(chapter, {"stage": "done", "message": "Execução interrompida por segurança"})
            result = {"chapter": chapter, "status": "failed", "error": str(exc)}
            with lock:
                finished.add(chapter)
                report(chapter, {"stage": "done", "message": f"Capítulo {index}/{len(chapters)} bloqueado"})
            return result
        report(chapter, {"stage": "prepare", "message": f"Capítulo {index}/{len(chapters)}: iniciando"})
        try:
            result = _run_chapter(manga, chapter, job_id, report)
        except Exception as exc:
            result = {"chapter": chapter, "status": "failed", "error": str(exc)}
        with lock:
            finished.add(chapter)
            report(chapter, {"stage": "done", "message": f"Capítulo {index}/{len(chapters)}: {result['status']}"})
        return result

    with ThreadPoolExecutor(max_workers=min(3, len(chapters)), thread_name_prefix="auto-merge-level1") as worker:
        futures = [worker.submit(process, index, chapter) for index, chapter in enumerate(chapters, start=1)]
        results = [future.result() for future in as_completed(futures)]
    order = {chapter: index for index, chapter in enumerate(chapters)}
    results.sort(key=lambda item: order[item["chapter"]])
    return results
