"""Exclusive session lease for Central V1 and V2 launched by the root menu."""
from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import socket
import sys
import tempfile

from central_v2.backend.log_redaction import forward_redacted


LEASE_ENV = "FOMINHA_CENTRAL_SESSION_HELD"
LOCK_PATH = Path(tempfile.gettempdir()) / "fominha-central-session.lock"


@contextmanager
def central_session(lock_path: Path | None = None):
    """Hold a nonblocking process-wide lease until the central server exits."""
    lock_path = lock_path or LOCK_PATH
    descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Outra Central está aberta pelo menu fominha.") from exc
        yield
    finally:
        os.close(descriptor)


def run_central(command: list[str], cwd: Path, env: dict[str, str] | None = None) -> None:
    """Keep the menu lease and sanitize child output before reaching the terminal."""
    import subprocess

    child_env = dict(os.environ if env is None else env)
    child_env[LEASE_ENV] = "1"
    child_env["PYTHONUNBUFFERED"] = "1"
    with central_session():
        with subprocess.Popen(command, cwd=cwd, env=child_env, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                              errors="replace", bufsize=1) as process:
            forward_redacted(process.stdout, sys.stdout)
            process.wait()


def server_session():
    """Acquire a lease for direct V2 starts; menu-launched servers inherit it."""
    if os.environ.get(LEASE_ENV) == "1":
        from contextlib import nullcontext
        return nullcontext()
    return central_session()


def legacy_server_active() -> bool:
    """Detect an already-running V1 endpoint before V2 starts a write job."""
    port = int(os.environ.get("FOMINHA_PROCESSING_PORT", "8766"))
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.25):
            return True
    except OSError:
        return False
