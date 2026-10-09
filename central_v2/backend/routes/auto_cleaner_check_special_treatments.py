"""Synchronize the derived worklist after a Check decision is persisted."""
import json

from central_v2.backend.orchestration.textoff_merged.special_treatments_manifest import (
    rebuild_special_treatments,
)
from .response import RouteResponse


def rebuild_after_check(manga, document, chapter):
    try:
        rebuild_special_treatments(manga, document, chapter)
    except Exception as exc:
        body = {"ok": False, "scope": "check", "decision_persisted": True,
            "special_treatments_updated": False,
            "error": "A decisão do Check foi salva, mas Special Treatments não foi atualizado.",
            "manifest_error": str(exc)}
        return RouteResponse(500, json.dumps(body, ensure_ascii=False).encode("utf-8"))
    return None
