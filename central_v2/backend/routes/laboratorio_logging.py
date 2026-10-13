"""Structured operational events for experimental Laboratory treatments."""
from time import monotonic
from uuid import uuid4

from central_v2.backend.operational_log import emit, short_duration


_LABELS = {"degrade": "Degradê", "estilizado": "Artístico",
           "gradiente_suave": "Suave"}


def run_treatment_logged(treatment, payload, operation, *, correlation_id=None):
    source_run_id = correlation_id if isinstance(correlation_id, str) and correlation_id else None
    operation_id = source_run_id or uuid4().hex
    started = monotonic()
    emit("INFO", "tratamento iniciado", component="LAB", job_id=operation_id,
         tratamento=_LABELS.get(treatment, treatment), capítulo=payload.get("chapter"),
         página=payload.get("page"))
    emit("INFO", "tratamento em execução", component="LAB", job_id=operation_id,
         tratamento=_LABELS.get(treatment, treatment))
    try:
        result = operation()
    except Exception as error:
        _finish(operation_id, started, treatment, "failed", source_run_id=source_run_id,
                detail=type(error).__name__)
        raise
    run_id = result.get("run_id")
    failure = result.get("error") or {}
    reason = failure.get("error", "") if isinstance(failure, dict) else ""
    outcome = ("succeeded" if result.get("execution_status") == "succeeded" else
               "assisted" if treatment == "degrade" and "Nenhum componente autorizado" in reason else
               "ineligible" if "Nenhum componente" in reason and "intersect" in reason.lower()
               else "failed")
    _finish(operation_id, started, treatment, outcome, run_id=run_id,
            source_run_id=source_run_id,
            detail=failure.get("type") if isinstance(failure, dict) else None)
    return result


def _finish(operation_id, started, treatment, outcome, *, run_id=None,
            source_run_id=None, detail=None):
    messages = {"succeeded": ("INFO", "tratamento concluído"),
                "assisted": ("INFO", "classificação aguardando autorização explícita"),
                "ineligible": ("WARNING", "nenhum componente elegível para o tratamento"),
                "failed": ("ERROR", "tratamento falhou")}
    level, message = messages[outcome]
    emit(level, message, component="LAB", job_id=source_run_id or operation_id,
         tratamento=_LABELS.get(treatment, treatment), run_id=run_id,
         execução_origem=source_run_id, duração=short_duration(monotonic() - started),
         detalhe=detail)


def treatment_blocked(treatment):
    emit("WARNING", "tratamento não iniciado: laboratório ocupado", component="LAB",
         tratamento=_LABELS.get(treatment, treatment))


def authorization_ready(run_id, candidate_count):
    emit("INFO", "componentes adiados disponíveis para revisão", component="LAB",
         job_id=run_id, run_id=run_id, componentes=candidate_count)


def authorization_unavailable(run_id):
    emit("WARNING", "nenhum componente adiado elegível para autorização",
         component="LAB", job_id=run_id, run_id=run_id)
