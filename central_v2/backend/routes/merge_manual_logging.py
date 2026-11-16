"""Business-event logs for saved manual-merge proposal application."""
import time

from central_v2.backend.operational_log import emit, short_duration


def log_apply_started(chapter: str, proposal_id: str) -> tuple[dict, float]:
    fields = {"capítulo": chapter, "proposta": proposal_id}
    started = time.monotonic()
    emit("INFO", "efetivação de faixa iniciada", component="MERGE-MANUAL", **fields)
    return fields, started


def log_apply_finished(result: dict, fields: dict, started: float) -> None:
    source_range = result.pop("source_range", None)
    combined_ranges = result.pop("selected_range_count", None)
    if result.get("status") == "FAIXA_SELECIONADA":
        event = "faixa já confirmada" if result.get("already_selected") else "faixa confirmada"
    elif result.get("already_applied"):
        event = "proposta já efetivada"
    else:
        event = "composição final publicada"
    emit("INFO", event, component="MERGE-MANUAL", **{
        **fields, "faixa": source_range,
        "faixas_restantes": result.get("remaining_intervals"),
        "faixas_combinadas": combined_ranges,
        "imagens_merge": result.get("merged_images"),
        "repetida": result.get("already_applied", result.get("already_selected", False)),
        "duração": short_duration(time.monotonic() - started),
    })


def log_apply_failed(error: Exception, fields: dict, started: float,
                     *, unexpected: bool = False) -> None:
    message = "falha inesperada ao efetivar faixa" if unexpected else "efetivação da faixa falhou"
    details = {**fields, "erro": str(error), "duração": short_duration(time.monotonic() - started)}
    if unexpected:
        details["tipo"] = type(error).__name__
    emit("ERROR", message, component="MERGE-MANUAL", **details)
