"""Single-worker in-memory job lifecycle for long V2 operations."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from datetime import datetime, timezone
import threading
import time
import uuid

from central_v2.backend.operational_log import bind_operation, emit, short_duration


_lock = threading.RLock()
_worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="central-v2-job")
_jobs = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _copy(job: dict) -> dict:
    public = {key: value for key, value in job.items() if not key.startswith("_")}
    return {**public, "progress": dict(job["progress"]), "results": list(job["results"])}


def _run(job_id: str, operation, component: str | None = None) -> None:
    component = component if component in {"SOMMELIER", "CLEANER-I", "COMBO"} else None
    def update(chapter: str, progress: dict) -> None:
        with _lock:
            job = _jobs[job_id]
            job["chapter"] = chapter
            current_progress = dict(progress)
            if component == "CLEANER-I" and int(current_progress.get("percent") or 0) >= 100:
                current_progress["percent"] = 99
            job["progress"] = current_progress
            job["updated_at"] = _now()
            percent = int(progress.get("percent") or 0)
            stage = progress.get("stage")
            if stage in {"page_started", "page"}:
                marker = (chapter, stage, progress.get("page_index"))
            else:
                marker = (chapter, stage, percent // 25)
            if marker != job.get("_terminal_marker"):
                job["_terminal_marker"] = marker
                message = progress.get("message") or progress.get("stage") or "Processando"
                if component == "SOMMELIER" and stage == "page":
                    emit("INFO", "página concluída", **{
                        "capítulo": chapter,
                        "página": f"{progress.get('completed', 0)}/{progress.get('total', 0)}",
                        "duração": (short_duration(progress["duration"])
                                    if progress.get("duration") is not None else None),
                        "balões": progress.get("bubbles"),
                        "candidatos": progress.get("candidates"),
                    })
                elif component == "CLEANER-I" and stage == "clean":
                    # The wrapper emits real Cleaner stage transitions; polling remains UI-only.
                    pass
                elif component:
                    pass
                else:
                    emit("INFO", message, component="CENTRAL", job_id=job_id,
                         progresso=f"{percent}%", capítulo=chapter)

    with _lock:
        _jobs[job_id]["status"] = "running"
        _jobs[job_id]["updated_at"] = _now()
        expected_chapters = int(_jobs[job_id]["progress"].get("total") or 0)
    operation_started = time.perf_counter()
    context = bind_operation(component, job_id) if component else nullcontext()
    with context:
        if component:
            emit("INFO", "execução iniciada", **{"capítulos": expected_chapters})
        else:
            emit("INFO", "execução iniciada", component="CENTRAL", job_id=job_id,
                 capítulos=expected_chapters)
        try:
            results = operation(update, job_id)
            failures = [item for item in results if isinstance(item, dict) and item.get("status") == "failed"]
            status = "failed" if failures else "completed"
            error = (f"{len(failures)} de {len(results)} capítulo(s) falharam. "
                     + "; ".join(str(item.get("error") or f"Cap. {item.get('chapter', '?')}")
                                  for item in failures)) if failures else ""
        except Exception as exc:
            results, status, error = [], "failed", str(exc)
    with _lock:
        job = _jobs[job_id]
        job.update(status=status, error=error, results=results, updated_at=_now())
        if component == "CLEANER-I" and status == "completed":
            job["progress"]["percent"] = 100
    summary = error or (f"{len(results)} capítulo(s)" if results else status)
    summary_fields = {"capítulos": len(results),
                      "duração": short_duration(time.perf_counter() - operation_started)}
    if component == "SOMMELIER":
        summary_fields.update(
            **{
                "páginas": sum(int(item.get("pages") or 0) for item in results if isinstance(item, dict)),
                "balões": sum(int(item.get("balloons") or 0) for item in results if isinstance(item, dict)),
            },
            candidatos=sum(int(item.get("candidates") or 0) for item in results if isinstance(item, dict)),
        )
    elif component == "CLEANER-I":
        summary_fields.update(
            **{"páginas": sum(int(item.get("pages") or 0) for item in results if isinstance(item, dict))},
            saidas=sum(int(item.get("outputs") or 0) for item in results if isinstance(item, dict)),
        )
    log_component = component or "CENTRAL"
    if status == "failed":
        emit("ERROR", "falha na execução", component=log_component, job_id=job_id,
             erro=summary, **summary_fields)
    else:
        emit("INFO", "execução concluída", component=log_component, job_id=job_id,
             resultado=summary, **summary_fields)


def submit(operation, total: int = 0, component: str | None = None, *, job_id=None) -> dict:
    job_id = job_id or uuid.uuid4().hex
    if (not isinstance(job_id, str) or len(job_id) != 32
            or any(char not in "0123456789abcdef" for char in job_id)):
        raise ValueError("Identificador de job inválido.")
    job = {
        "id": job_id, "status": "queued", "chapter": "",
        "progress": {"completed": 0, "total": total, "value": 0, "max": total,
                     "percent": 0, "message": "Na fila para execução"},
        "results": [], "error": "", "created_at": _now(), "updated_at": _now(),
        "_component": component,
    }
    with _lock:
        if job_id in _jobs:
            raise ValueError("Identificador de job já utilizado.")
        _jobs[job_id] = job
        _worker.submit(_run, job_id, operation, component)
    return _copy(job)


def get_job(job_id: str) -> dict | None:
    with _lock:
        job = _jobs.get(job_id)
        return _copy(job) if job else None
