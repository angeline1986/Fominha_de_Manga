"""Persistent job adapter over Central V2's serialized worker and Combo result store."""
import json
import threading
import uuid

from central_v2.backend.jobs.manager import submit
from central_v2.backend.operational_log import emit
from .api_contract import request_context, summarize_plan, verify_plan_token
from .execution import source_signature
from .orchestrator import run_combo
from .job_store import (ensure_area, now, persisted_job, persisted_result,
                        run_root as workspace_for_job, save)
from .run_result_store import read_result
_reservation_lock = threading.Lock()
_reserved_manga = set()


def start_job(payload, output_root):
    fields = {"provider", "manga", "chapters", "plan_token"}
    if isinstance(payload, dict) and "resume_job_id" in payload:
        if not isinstance(payload["resume_job_id"], str):
            raise ValueError("Identificador de retomada inválido.")
        fields.add("resume_job_id")
    context = request_context(payload, output_root, fields=fields)
    verify_plan_token(payload["plan_token"], context)
    planned = run_combo(context["manga"], context["provider"], context["chapters"], None,
                        mode="PLAN_ONLY")
    ensure_area("jobs")
    source_key = str(context["manga"])
    previous = _resume_state(payload.get("resume_job_id"), context, output_root)
    job_id = previous["id"] if previous else uuid.uuid4().hex
    with _reservation_lock:
        if source_key in _reserved_manga:
            raise ValueError("Já existe um job Combo em execução para esta obra.")
        _reserved_manga.add(source_key)
    state = previous or {"id": job_id, "provider": context["provider"],
        "manga": context["manga_name"], "source": source_key,
        "chapters": context["chapters"], "source_signature": context["signature"],
        "chapter_states": [{"chapter": chapter, "status": "PENDING",
            "solids": "PENDING", "glass": "PENDING", "combo": "PENDING"}
            for chapter in context["chapters"]], "created_at": now()}
    state.update(status="queued", stage="PREPARING", page=None, chapter=None,
        pages_total=summarize_plan(planned.get("plan") or {})["pages_total"], errors=[])
    state.setdefault("pages_completed", 0)
    state.setdefault("pages_blocked", 0)
    try:
        save(state)
        submit(lambda progress, identifier: _run_job(context, state, progress),
               total=len(context["chapters"]), job_id=job_id, component="COMBO")
    except Exception:
        with _reservation_lock:
            _reserved_manga.discard(source_key)
        state.update(status="FAILED", errors=[{"reason": "JOB_SUBMISSION_FAILED"}])
        save(state)
        raise
    emit("INFO", "Combo Turbo job aceito", component="COMBO", job_id=job_id,
         provider=context["provider"], obra=context["manga_name"],
         capitulos=context["chapters"], workspace=f"runs/{job_id}")
    return {key: state[key] for key in ("id", "status", "created_at", "chapters", "stage")}


def _resume_state(job_id, context, output_root):
    if job_id is None:
        return None
    previous = persisted_job(job_id)
    if (previous is None or previous.get("status") != "interrupted"
            or previous.get("provider") != context["provider"]
            or previous.get("manga") != context["manga_name"]
            or previous.get("chapters") != context["chapters"]
            or previous.get("source_signature") != context["signature"]):
        raise ValueError("Job não interrompido, obsoleto ou incompatível para retomada.")
    status, stored = persisted_result(job_id, output_root)
    if status != 200 or not isinstance(stored.get("result"), dict):
        raise ValueError("Resultado interrompido inválido; não é possível retomar.")
    return previous


def _run_job(context, state, progress):
    job_id, source = state["id"], context["manga"]
    completed, blocked = set(), set()
    try:
        ensure_area("runs")
        run_root = workspace_for_job(job_id)
        state.update(status="running", stage="PREPARING")
        save(state)
        if source_signature(source, context["provider"], context["chapters"]) != context["signature"]:
            raise ValueError("PLAN_CONTEXT_CHANGED")

        def update(event):
            stage = event.get("stage", "RUNNING")
            prior_stage = state.get("stage")
            state["stage"] = {"start": "PREPARING", "validation": "VALIDATING",
                               "complete": "COMPLETED"}.get(stage, str(stage).upper())
            state["chapter"] = event.get("chapter")
            state["page"] = event.get("page")
            chapter_state = next((row for row in state["chapter_states"]
                                  if row["chapter"] == event.get("chapter")), None)
            if chapter_state:
                if stage == "start":
                    chapter_state.update(status="RUNNING", combo="RUNNING")
                elif stage in {"SOLIDOS", "GLASS"}:
                    chapter_state[stage.lower()] = event.get("status", "RUNNING")
                elif stage == "COMPOSING":
                    chapter_state["combo"] = "COMPOSING"
                elif stage == "chapter_complete":
                    chapter_state.update(status=event.get("status"), combo=event.get("status"))
            if state["stage"] != prior_stage or stage == "complete":
                emit("INFO", "Combo Turbo progresso", component="COMBO", job_id=job_id,
                     capítulo=state["chapter"], página=state["page"],
                     etapa=state["stage"], estado=event.get("status"))
            if stage == "complete" and event.get("page"):
                key = (event.get("chapter"), event["page"])
                completed.add(key)
                state["pages_completed"] = len(completed)
                if event.get("status") in {"BLOCKED", "INVALID", "FAILED", "CONFLICT"}:
                    blocked.add(key)
                    state["pages_blocked"] = len(blocked)
            save(state)
            progress(str(event.get("chapter") or "lote"), {
                "stage": state["stage"], "message": state["stage"],
                "completed": state["pages_completed"], "total": state["pages_total"]})

        record = run_combo(source, context["provider"], context["chapters"], run_root,
                           mode="ISOLATED_RUN", progress=update)
        if source_signature(source, context["provider"], context["chapters"]) != context["signature"]:
            raise ValueError("SOURCE_CHANGED_DURING_JOB")
        result_path = run_root / "combo-run-result.json"
        if result_path.is_file():
            marker = json.loads((run_root / ".combo-workspace.json").read_text(encoding="utf-8"))
            if marker.get("signature") != context["signature"]:
                raise ValueError("SOURCE_SIGNATURE_MISMATCH")
            verified = read_result(run_root, run_id=marker["run_id"],
                provider=context["provider"], manga=source, chapters=context["chapters"],
                signature=context["signature"])
            state["result_status"] = verified["status"]
            state["status"] = verified["status"].lower()
            state["errors"] = verified.get("errors", [])
            state["chapter_states"] = [_chapter_status(row) for row in verified["results"]]
            final_pages = [page for row in verified["results"] for page in row.get("pages", [])]
            state["pages_completed"] = len(final_pages)
            state["pages_blocked"] = sum(page.get("status") in
                {"BLOCKED", "INVALID", "FAILED", "CONFLICT"} for page in final_pages)
            for row in verified["results"]:
                emit("INFO", "Combo Turbo capítulo concluído", component="COMBO", job_id=job_id,
                     capítulo=row["chapter"], estado=row["status"],
                     páginas_compostas=sum(page.get("status") == "COMPOSED" for page in row["pages"]),
                     conflitos=sum(page.get("status") == "CONFLICT" for page in row["pages"]),
                     reutilizáveis=sum(sum(item.get("reused", False)
                         for item in page.get("treatments", {}).values()) for page in row["pages"]))
        else:
            state["status"] = record.get("status", "FAILED").lower()
            state["errors"] = record.get("errors", [])
        state["stage"] = "COMPLETED" if state["status"] in {"completed", "partial"} else state["status"].upper()
        state["result_path"] = f"runs/{job_id}/combo-run-result.json" if result_path.is_file() else None
        save(state)
        emit("INFO", "Combo Turbo job finalizado", component="COMBO", job_id=job_id,
             status=state["status"], paginas_concluidas=state["pages_completed"],
             paginas_bloqueadas=state["pages_blocked"])
        if state["status"] in {"partial", "blocked", "failed"}:
            return [{"chapter": "lote", "status": "failed",
                     "error": f"Combo Turbo terminou com estado {state['status']}."}]
        return record.get("results", [])
    except Exception as exc:
        state.update(status="failed", stage="FAILED", errors=[{"reason": str(exc)}])
        save(state)
        emit("ERROR", "Combo Turbo job falhou", component="COMBO", job_id=job_id, erro=str(exc))
        return [{"status": "failed", "error": str(exc)}]
    finally:
        with _reservation_lock:
            _reserved_manga.discard(str(source))


def _chapter_status(row):
    pages = row.get("pages", [])
    values = {"chapter": row.get("chapter"), "status": row.get("status"),
              "combo": row.get("status")}
    for stage in ("solids", "glass"):
        statuses = [page.get(stage, {}).get("status") if page.get("eligible", {}).get(stage.upper())
                    else "NO_WORK" for page in pages]
        if not statuses or all(item == "NO_WORK" for item in statuses):
            values[stage] = "NO_WORK"
        elif any(item in {"BLOCKED", "INVALID", "UNVERIFIED"} for item in statuses):
            values[stage] = "BLOCKED"
        elif any(item in {"FAILED", "MISSING", "STALE"} for item in statuses):
            values[stage] = "FAILED"
        else:
            values[stage] = "REUSABLE"
    return values
