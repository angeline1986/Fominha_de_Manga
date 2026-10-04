"""Compact, human-readable logs for scoped Central V2 operations."""
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime
import json
import re


_operation = ContextVar("central_v2_operation_log", default=None)


@contextmanager
def bind_operation(component: str, job_id: str):
    token = _operation.set((component, job_id))
    try:
        yield
    finally:
        _operation.reset(token)


def emit(level: str, message: str, *, component: str | None = None,
         job_id: str | None = None, **fields) -> str:
    bound = _operation.get()
    if bound:
        component = component or bound[0]
        job_id = job_id or bound[1]
    component = component or "CENTRAL"
    stamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    identity = f"[{component}]"
    if job_id:
        identity += f"[{job_id[:6]}]"
    line = f"{stamp} {level.upper()} {identity} {_single_line(message)}"
    if fields:
        values = " ".join(f"{key}={_value(value)}" for key, value in fields.items())
        line += f" · {values}"
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
