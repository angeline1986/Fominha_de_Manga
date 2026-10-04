"""Consume the Cleaner Nível I stdout event protocol and retain diagnostics."""
import json
import queue
import threading

from central_v2.backend.operational_log import emit, short_duration

_STAGE_LABELS = {
    "preparacao": "preparação", "deteccao": "detecção", "ocr": "OCR",
    "mascaras": "máscaras", "denoise": "redução de ruído",
    "exportacao": "exportação",
}


def start_stream_readers(process):
    messages = queue.Queue()
    readers = [
        threading.Thread(target=_read_lines, args=(stream, name, messages), daemon=True)
        for stream, name in ((process.stdout, "stdout"), (process.stderr, "stderr"))
    ]
    for reader in readers:
        reader.start()
    return messages, readers


def consume_messages(messages, stdout_tail, stderr_tail):
    while True:
        try:
            source, line = messages.get_nowait()
        except queue.Empty:
            return
        if line is None:
            continue
        tail = stdout_tail if source == "stdout" else stderr_tail
        tail.append(line)
        del tail[:-30]
        if source == "stderr":
            emit("WARNING", "stderr do processo Nível I", origem=source, detalhe=line)
            continue
        _consume_event(line)


def _read_lines(stream, source, output):
    try:
        for line in stream:
            output.put((source, line.rstrip("\r\n")))
    finally:
        output.put((source, None))


def _consume_event(line):
    try:
        event = json.loads(line)
    except (ValueError, TypeError):
        emit("WARNING", "saída não estruturada do processo Nível I", detalhe=line)
        return
    if not isinstance(event, dict) or event.get("type") != "central_log":
        emit("WARNING", "evento inesperado do processo Nível I")
        return
    kind, stage = event.get("event"), event.get("stage")
    if kind == "started":
        emit("INFO", "capítulo iniciado", **{
            "capítulo": event.get("chapter"), "páginas": event.get("pages"),
        })
    elif kind == "stage_started":
        emit("INFO", "etapa iniciada", etapa=_STAGE_LABELS.get(stage, stage))
    elif kind == "stage_completed":
        emit("INFO", "etapa concluída", etapa=_STAGE_LABELS.get(stage, stage),
             **{"duração": short_duration(event.get("duration_seconds") or 0)})
    elif kind == "diagnostic":
        emit(event.get("level") or "WARNING", "diagnóstico do Cleaner",
             detalhe=event.get("message"))
    elif kind == "finished":
        emit("INFO", "lote do Cleaner concluído",
             **{"duração": short_duration(event.get("duration_seconds") or 0)})
    elif kind == "failed":
        emit("ERROR", "lote do Cleaner falhou", erro=event.get("error"),
             diagnostico=event.get("diagnostic"))
    else:
        emit("WARNING", "evento desconhecido do Cleaner", evento=kind)
