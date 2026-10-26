"""Compact, human-readable logs for scoped Central V2 operations."""
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime
import json
import os
import re

from central_v2.backend.log_redaction import redact_log_text


_operation = ContextVar("central_v2_operation_log", default=None)
_LEVELS = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40}
_MIN_LEVEL = _LEVELS.get(os.getenv("CENTRAL_V2_LOG_LEVEL", "INFO").upper(), 20)


@contextmanager
def bind_operation(component: str, job_id: str):
    token = _operation.set((component, job_id))
    try:
        yield
    finally:
        _operation.reset(token)


def emit(level: str, message: str, *, component: str | None = None,
         job_id: str | None = None, **fields) -> str:
    normalized_level = level.upper()
    if _LEVELS.get(normalized_level, 20) < _MIN_LEVEL:
        return ""
    bound = _operation.get()
    if bound:
        component = component or bound[0]
        job_id = job_id or bound[1]
    component = component or "CENTRAL"
    stamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    identity = f"[{component}]"
    if job_id:
        identity += f"[{job_id[:6]}]"
    line = f"{stamp} {normalized_level} {identity} {_single_line(message)}"
    if fields:
        values = " ".join(f"{key}={_value(value)}" for key, value in fields.items())
        line += f" · {values}"
    line = redact_log_text(line)
    print(line, flush=True)
    return line


def _single_line(value) -> str:
    return re.sub(r"\s+", " ", str(value)).strip()


def _value(value) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "sim" if value else "não"
    if isinstance(value, (int, float)):
        return str(value)
    normalized = _single_line(value)
    return normalized if normalized and not re.search(r"[\s=]", normalized) else json.dumps(normalized, ensure_ascii=False)


def short_duration(seconds) -> str:
    return f"{max(0.0, float(seconds)):.1f}s"
