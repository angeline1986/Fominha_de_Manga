"""Recover a concise, safe worker failure for the Central job result."""
from __future__ import annotations

import json
from pathlib import Path

from central_v2.backend.log_redaction import redact_log_text


def failure_message(progress_path: Path, code: int, chapters: list[str]) -> str:
    fallback = f"Nível II encerrou sem resultado validado (código {code})."
    try:
        payload = json.loads(progress_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return fallback
    if (not isinstance(payload, dict) or payload.get("status") != "failed"
            or str(payload.get("chapter")) not in chapters):
        return fallback
    error = payload.get("error")
    if not isinstance(error, str) or not error.strip():
        return fallback
    chapter = str(payload["chapter"])
    reason = " ".join(redact_log_text(error).split())[:300]
    page = payload.get("page")
    if isinstance(page, str) and page and page not in reason and Path(page).name == page:
        reason = f"Página {page}: {reason}"
    return f"Cap. {chapter}: {reason}"
