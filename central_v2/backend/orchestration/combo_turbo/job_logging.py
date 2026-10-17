"""Compact operational events for Combo Turbo jobs."""
from central_v2.backend.operational_log import emit


def log_progress(job_id, stage, prior_stage, state, event):
    if (state["stage"] != prior_stage
            and stage not in {"validation", "COMPOSING", "complete"}):
        emit("INFO", "Combo Turbo progresso", component="COMBO", job_id=job_id,
             capítulo=state["chapter"], página=state["page"],
             etapa=state["stage"], estado=event.get("status"))


def log_page_outcome(job_id, event):
    status = event.get("status")
    fields = {"component": "COMBO", "job_id": job_id,
              "capítulo": event.get("chapter"), "página": event.get("page"),
              "estado": status}
    if status in {"CONFLICT", "BLOCKED", "INVALID"}:
        emit("WARNING", "resultado de página inconsistente", **fields)
    elif status == "FAILED":
        emit("ERROR", "falha de processamento da página", **fields)
