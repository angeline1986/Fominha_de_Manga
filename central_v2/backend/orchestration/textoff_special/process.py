"""Launch and stop the complete isolated preview process tree."""
import os
import json
from pathlib import Path
import signal
import subprocess
import time

from .catalog import ROOT, python_for


def run_worker(key: str, request_path: Path, log_path: Path, timeout: float = 1800,
               on_progress=None) -> None:
    command = [str(python_for(key)), "-u", "-m",
               "central_v2.backend.orchestration.textoff_special.worker",
               "--request", str(request_path)]
    environment = os.environ.copy()
    environment.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", PYTHONUNBUFFERED="1")
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(command, cwd=ROOT, env=environment, stdout=log,
                                   stderr=subprocess.STDOUT, start_new_session=(os.name == "posix"))
        try:
            code = _wait_for_worker(process, timeout, request_path, on_progress)
        except BaseException:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                if os.name == "posix":
                    os.killpg(process.pid, signal.SIGKILL)
                else:
                    process.kill()
                process.wait()
            raise
    if code:
        raise RuntimeError(f"Worker de Casos Especiais falhou ({code}); consulte {log_path}.")


def _wait_for_worker(process, timeout, request_path: Path, on_progress):
    if on_progress is None:
        return process.wait(timeout=timeout)
    progress_file = request_path.parent / "treatment/cleaner-progress.json"
    last_payload = None
    deadline = time.monotonic() + timeout
    while True:
        try:
            payload = json.loads(progress_file.read_text(encoding="utf-8"))
            if payload != last_payload:
                last_payload = payload
                overall = max(0.0, min(1.0, float(payload.get("overall") or 0.0)))
                on_progress({"percent": int(5 + overall * 75 + 0.5),
                             "stage": str(payload.get("stage") or "cleaner"),
                             "message": str(payload.get("detail") or "Cleaner V2 processando...")})
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            pass
        try:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return process.wait(timeout=0)
            return process.wait(timeout=min(0.25, remaining))
        except subprocess.TimeoutExpired:
            if time.monotonic() >= deadline:
                raise


def install_worker_cleanup() -> None:
    """The Cleaner can start its own session, so process-group killing is insufficient."""
    import psutil

    def stop(signum, _frame):
        children = psutil.Process().children(recursive=True)
        for child in reversed(children):
            try:
                child.terminate()
            except psutil.NoSuchProcess:
                pass
        _, alive = psutil.wait_procs(children, timeout=5)
        for child in alive:
            try:
                child.kill()
            except psutil.NoSuchProcess:
                pass
        raise SystemExit(128 + signum)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
