"""Durable Combo job snapshots and integrity-checked result lookup."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import tempfile

from central_v2.backend.jobs.manager import get_job
from central_v2.backend.state.manga_state import resolve_manga

from .execution import source_signature
from .orchestrator_workspace import _reject_links
from .run_result_store import read_result, write_json_atomic

STATE_ROOT = Path(tempfile.gettempdir()).resolve() / "fominha-central-v2-combo-turbo"
_JOB_ID = re.compile(r"[a-f0-9]{32}\Z")


def save(state):
    state["updated_at"] = now()
    folder = job_path(state["id"]).parent
    if folder.is_symlink():
        raise ValueError("Diretório de job Combo aponta por link simbólico.")
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not folder.resolve().is_relative_to(STATE_ROOT.resolve()):
        raise ValueError("Diretório de job Combo fora da raiz autorizada.")
    canonical = json.dumps(state, ensure_ascii=False, sort_keys=True,
                           separators=(",", ":")).encode("utf-8")
    write_json_atomic(job_path(state["id"]), {"sha256": hashlib.sha256(canonical).hexdigest(),
                                               "job": json.loads(canonical)})


def persisted_job(job_id):
    if not isinstance(job_id, str) or not _JOB_ID.fullmatch(job_id):
        return None
    try:
        safe_job_path(job_id)
        envelope = json.loads(job_path(job_id).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    state = envelope.get("job") if isinstance(envelope, dict) else None
    canonical = json.dumps(state, ensure_ascii=False, sort_keys=True,
                           separators=(",", ":")).encode("utf-8") if isinstance(state, dict) else b""
    digest = envelope.get("sha256") if isinstance(envelope, dict) else None
    if hashlib.sha256(canonical).hexdigest() != digest:
        return None
    if not isinstance(state, dict) or state.get("id") != job_id:
        return None
    if state.get("status") in {"queued", "running"} and get_job(job_id) is None:
        state["status"] = "interrupted"
        state["stage"] = "INTERRUPTED"
        state["errors"] = [{"reason": "SERVER_RESTARTED_DURING_JOB"}]
    return state


def public_job(job_id):
    state = persisted_job(job_id)
    if state is None:
        return None
    keys = ("id", "status", "provider", "manga", "chapters", "chapter_states", "stage",
            "chapter", "page", "pages_total", "pages_completed", "pages_blocked",
            "errors", "created_at", "updated_at")
    result = {key: state.get(key) for key in keys}
    result["progress"] = {"stage": state.get("stage"), "chapter": state.get("chapter"),
        "page": state.get("page"), "completed": state.get("pages_completed", 0),
        "total": state.get("pages_total", 0), "percent": None}
    return result


def persisted_result(job_id, output_root):
    state = persisted_job(job_id)
    if state is None:
        return 404, {"error": "Job Combo Turbo não encontrado."}
    try:
        root = run_root(job_id)
    except ValueError:
        return 409, {"job_id": job_id, "status": "INVALID", "reason": "WORKSPACE_OUTSIDE_ROOT"}
    path = root / "combo-run-result.json"
    marker_path = root / ".combo-workspace.json"
    if path.is_symlink() or marker_path.is_symlink():
        return 409, {"job_id": job_id, "status": "INVALID", "reason": "SYMLINK_IN_RESULT"}
    if not path.is_file():
        if state.get("result_path"):
            return 409, {"job_id": job_id, "status": "INVALID", "reason": "PERSISTED_RESULT_MISSING"}
        return 200, {"job_id": job_id, "status": state["status"],
                     "errors": state.get("errors", []), "results": []}
    try:
        manga = resolve_manga(output_root, state["provider"], state["manga"])
        signature = source_signature(manga, state["provider"], state["chapters"])
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
        if (marker.get("source") != str(manga) or marker.get("provider") != state["provider"]
                or marker.get("chapters") != state["chapters"]):
            raise ValueError("Workspace identity changed.")
        _reject_links(manga)
        result = read_result(root, run_id=marker["run_id"], provider=state["provider"],
            manga=manga, chapters=state["chapters"], signature=marker["signature"])
        if signature != marker.get("signature"):
            return 409, {"job_id": job_id, "status": "STALE", "reason": "SOURCE_SIGNATURE_CHANGED"}
        if state["status"] == "interrupted":
            result["status"] = "INTERRUPTED"
            result.setdefault("errors", []).append({"reason": "SERVER_RESTARTED_DURING_JOB"})
            return 200, {"job_id": job_id, "status": "INTERRUPTED", "result": result}
        return 200, {"job_id": job_id, "status": state["status"], "result": result}
    except (OSError, ValueError, TypeError, KeyError, RuntimeError):
        return 409, {"job_id": job_id, "status": "INVALID", "reason": "PERSISTED_RESULT_INVALID"}


def job_path(job_id):
    return STATE_ROOT / "jobs" / job_id / "job.json"


def safe_job_path(job_id):
    root, folder = STATE_ROOT.resolve(), STATE_ROOT / "jobs" / job_id
    if (STATE_ROOT.is_symlink() or (STATE_ROOT / "jobs").is_symlink()
            or folder.is_symlink() or not folder.resolve().is_relative_to(root)):
        raise ValueError("Registro Combo fora da raiz autorizada.")


def run_root(job_id):
    candidate = STATE_ROOT / "runs" / job_id
    if (STATE_ROOT.is_symlink() or (STATE_ROOT / "runs").is_symlink()
            or candidate.is_symlink()):
        raise ValueError("Workspace Combo aponta por link simbólico.")
    root = candidate.resolve()
    if not root.is_relative_to(STATE_ROOT.resolve()):
        raise ValueError("Workspace Combo fora da raiz autorizada.")
    return root


def ensure_area(name):
    if STATE_ROOT.is_symlink():
        raise ValueError("Raiz de jobs Combo aponta por link simbólico.")
    STATE_ROOT.mkdir(mode=0o700, parents=True, exist_ok=True)
    area = STATE_ROOT / name
    if area.is_symlink():
        raise ValueError("Área de jobs Combo aponta por link simbólico.")
    area.mkdir(mode=0o700, exist_ok=True)
    if not area.resolve().is_relative_to(STATE_ROOT.resolve()):
        raise ValueError("Área de jobs Combo fora da raiz autorizada.")


def now():
    return datetime.now(timezone.utc).isoformat()
