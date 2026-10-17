"""PLAN_ONLY and disposable ISOLATED_RUN entry points for Combo Turbo."""
import json
import shutil
from pathlib import Path
import uuid

from central_v2.backend.operational_log import emit

from .orchestrator_chapter import _count_states, _notify, _run_chapter, _run_status
from .orchestrator_workspace import _reject_links, _safe_roots
from .execution import run_glass_isolated, run_solids_isolated, source_signature
from .planner import plan_combo
from .run_result_store import (SCHEMA, blocked_chapter, new_run_id, new_run_result,
    page_record, read_result, set_chapter_result, write_json_atomic, write_result)


def run_combo(manga, provider, chapters, output_dir, *, mode="PLAN_ONLY", progress=None):
    """Plan or execute a selected chapter set using only disposable paths."""
    selected_mode = str(mode).upper() if isinstance(mode, str) else ""
    if selected_mode == "PLAN_ONLY":
        _notify(progress, {"stage": "PLANNING", "status": "RUNNING"})
        plan = plan_combo(manga, provider, chapters)
        _notify(progress, {"stage": "PLANNING", "status": plan["status"]})
        return {"mode": selected_mode, "status": plan["status"], "plan": plan,
                "results": [], "errors": []}
    if selected_mode != "ISOLATED_RUN":
        return _failure(selected_mode, "UNKNOWN_MODE")
    source = Path(manga).resolve()
    destination = Path(output_dir).resolve() if output_dir is not None else None
    if not _safe_roots(source, destination, provider, chapters):
        return _failure(selected_mode, "DISPOSABLE_OUTPUT_REQUIRED")
    try:
        _reject_links(source)
        signature = source_signature(source, provider, chapters)
    except (OSError, ValueError, TypeError, RuntimeError):
        return _failure(selected_mode, "SOURCE_AUTHORITY_UNAVAILABLE")
    marker = destination / ".combo-workspace.json"
    workspace = destination / ".combo-workspace"
    clone = workspace / source.name
    plan = None
    record = None
    try:
        if destination.exists():
            saved = json.loads(marker.read_text(encoding="utf-8"))
            if (saved.get("source") != str(source) or saved.get("signature") != signature
                    or saved.get("provider") != provider or saved.get("chapters") != list(chapters)
                    or not clone.is_dir() or clone.is_symlink()):
                return _failure(selected_mode, "RESUME_SOURCE_CHANGED")
        plan = plan_combo(source, provider, chapters)
        _notify(progress, {"stage": "PREPARING", "status": "RUNNING"})
        if not destination.exists():
            destination.mkdir(parents=True, exist_ok=False)
            workspace.mkdir()
            shutil.copytree(source, clone)
            if source_signature(source, provider, chapters) != signature:
                raise RuntimeError("SOURCE_CHANGED_DURING_SNAPSHOT")
            saved = {"source": str(source), "signature": signature, "provider": provider,
                     "chapters": list(chapters), "run_id": uuid.uuid4().hex}
            write_json_atomic(marker, saved)
        saved = json.loads(marker.read_text(encoding="utf-8"))
        run_id = saved.get("run_id")
        if not isinstance(run_id, str) or not run_id:
            saved["run_id"] = run_id = new_run_id()
            write_json_atomic(marker, saved)
        resume_plan = plan_combo(clone, provider, chapters, repair_isolated_outputs=True)
        try:
            record = read_result(destination, run_id=run_id, provider=provider,
                manga=source, chapters=chapters, signature=signature)
        except FileNotFoundError:
            record = new_run_result(run_id, provider, source, chapters, destination, signature)
        record.update(mode=selected_mode, plan=resume_plan, status="RUNNING")
        record.setdefault("publication", [])
        write_result(destination, record)
        for chapter_plan in resume_plan["chapters"]:
            chapter = chapter_plan["chapter"]
            _notify(progress, {"chapter": chapter, "stage": "start", "status": "RUNNING"})
            if chapter_plan.get("status") == "BLOCKED" and not chapter_plan.get("pages"):
                row = blocked_chapter(chapter_plan, "CHAPTER_PLAN_BLOCKED")
                set_chapter_result(record, row)
                record["errors"].extend(row["errors"])
                write_result(destination, record)
                _notify(progress, {"chapter": chapter, "stage": "chapter_complete",
                                   "status": "BLOCKED"})
                continue
            page_rows = {}
            def save_page(outcome, planned):
                normalized = page_record(provider, clone.name, chapter, planned,
                                         outcome, destination)
                page_rows[outcome["page"]] = normalized
                interim = {"chapter": chapter, "status": "RUNNING",
                           "pages": list(page_rows.values()), "errors": []}
                set_chapter_result(record, interim)
                write_result(destination, record)
            try:
                raw = _run_chapter(clone, provider, chapter, chapter_plan, destination,
                                   progress, page_callback=save_page)
                status = raw["status"]
                row = {"chapter": chapter, "status": status,
                       "pages": list(page_rows.values()), "errors": raw.get("errors", [])}
            except (OSError, ValueError, TypeError, RuntimeError) as exc:
                row = {"chapter": chapter, "status": "FAILED", "pages": [],
                       "errors": [{"reason": "CHAPTER_EXECUTION_FAILED", "detail": str(exc)}]}
            row["counts"] = _count_states(row["pages"])
            set_chapter_result(record, row)
            record["errors"] = [error for item in record["results"]
                                for error in item.get("errors", [])]
            write_result(destination, record)
        record["status"] = _run_status(record["results"], record.get("errors", []))
        record["experimental_root"], record["resumable"] = str(destination), True
        write_result(destination, record)
        from .publication import publish_combo
        for row in record["results"]:
            if not row.get("pages") or row.get("status") not in {"COMPLETED", "PARTIAL"}:
                continue
            _notify(progress, {"chapter": row["chapter"], "stage": "PUBLISHING_ISOLATED",
                               "status": "RUNNING"})
            try:
                outcome = publish_combo(clone, destination, row["chapter"], record,
                                        run_id=run_id)
            except (OSError, ValueError, TypeError, RuntimeError) as exc:
                outcome = {"status": "FAILED", "run_id": run_id,
                           "reasons": ["PUBLICATION_FAILED"], "detail": str(exc)}
            record["publication"] = [item for item in record["publication"]
                                     if item.get("chapter") != row["chapter"]]
            record["publication"].append({"chapter": row["chapter"], **outcome})
            if outcome.get("status") in {"PARTIAL", "BLOCKED", "FAILED", "INVALID"}:
                record["status"] = "PARTIAL"
                if outcome.get("status") in {"FAILED", "INVALID"}:
                    record.setdefault("errors", []).append({"chapter": row["chapter"],
                        "reason": "ISOLATED_PUBLICATION_FAILED",
                        "detail": outcome.get("detail") or outcome.get("reasons")})
            write_result(destination, record)
        _notify(progress, {"stage": "COMPLETED", "status": record["status"]})
        return record
    except (OSError, ValueError, TypeError, RuntimeError) as exc:
        emit("ERROR", "Combo isolado bloqueado", component="COMBO", erro=str(exc))
        if isinstance(record, dict):
            record["status"] = "FAILED"
            record.setdefault("errors", []).append({
                "reason": "ISOLATION_OR_EXECUTION_FAILED", "detail": str(exc)})
            try:
                write_result(destination, record)
            except (OSError, ValueError, TypeError):
                pass
            return record
        return _failure(selected_mode, "ISOLATION_OR_EXECUTION_FAILED", detail=str(exc))






def _failure(mode, reason):
    return {"mode": mode, "status": "BLOCKED", "plan": None, "results": [],
            "errors": [{"reason": reason}]}
