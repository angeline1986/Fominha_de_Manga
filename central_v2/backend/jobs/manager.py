"""Single-worker in-memory job lifecycle for long V2 operations."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import threading
import uuid


_lock = threading.RLock()
_worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="central-v2-job")
_jobs = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _copy(job: dict) -> dict:
    public = {key: value for key, value in job.items() if not key.startswith("_")}
    return {**public, "progress": dict(job["progress"]), "results": list(job["results"])}


def _run(job_id: str, operation) -> None:
    def update(chapter: str, progress: dict) -> None:
        with _lock:
            job = _jobs[job_id]
            job["chapter"] = chapter
            job["progress"] = dict(progress)
            job["updated_at"] = _now()
            percent = int(progress.get("percent") or 0)
            marker = (chapter, progress.get("stage"), percent // 25)
            if marker != job.get("_terminal_marker"):
                job["_terminal_marker"] = marker
                message = progress.get("message") or progress.get("stage") or "Processando"
                print(f"[central-v2][job {job_id[:8]}] {percent}% · {chapter}: {message}", flush=True)

    with _lock:
        _jobs[job_id]["status"] = "running"
        _jobs[job_id]["updated_at"] = _now()
    print(f"[central-v2][job {job_id[:8]}] execução iniciada", flush=True)
    try:
        results = operation(update, job_id)
        status, error = "completed", ""
    except Exception as exc:
        results, status, error = [], "failed", str(exc)
    with _lock:
        job = _jobs[job_id]
        job.update(status=status, error=error, results=results, updated_at=_now())
    summary = f"{len(results)} capítulo(s)" if results else error or status
    print(f"[central-v2][job {job_id[:8]}] {status}: {summary}", flush=True)


def submit(operation, total: int = 0) -> dict:
    job_id = uuid.uuid4().hex
    job = {
        "id": job_id, "status": "queued", "chapter": "",
        "progress": {"completed": 0, "total": total, "value": 0, "max": total,
                     "percent": 0, "message": "Na fila para execução"},
        "results": [], "error": "", "created_at": _now(), "updated_at": _now(),
    }
    with _lock:
        _jobs[job_id] = job
        _worker.submit(_run, job_id, operation)
    return _copy(job)


def get_job(job_id: str) -> dict | None:
    with _lock:
        job = _jobs.get(job_id)
        return _copy(job) if job else None
