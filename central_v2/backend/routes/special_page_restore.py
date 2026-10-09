"""Preview and queue a confirmed whole-page special-treatment reset."""
import json
from pathlib import Path

from central_v2.backend.jobs.manager import submit
from central_v2.backend.orchestration.textoff_merged.special_page_restore import (
    images, inspect, proposal_version, restore,
)

from .response import RouteResponse
from .special_treatments import _manga

ROUTE = "/api/textoff/special/restore-page"


def _value(values, key):
    value = values.get(key)
    if isinstance(value, list):
        value = value[0] if len(value) == 1 else None
    if not isinstance(value, str) or not value:
        raise ValueError(f"Campo {key} inválido na restauração da página.")
    return value


def get_response(query: dict, output_root: Path, *, image=False) -> RouteResponse:
    try:
        provider, name, chapter, page = (_value(query, key)
            for key in ("provider", "manga", "chapter", "page"))
        manga = _manga(provider, name, output_root)
        proposal = inspect(manga, provider, chapter, page)
        if image:
            if _value(query, "version") != proposal["version"]:
                raise ValueError("Prévia de restauração obsoleta.")
            content = images(manga, provider, chapter, page, proposal, _value(query, "side"))
            return RouteResponse(200, content, "image/png")
        return RouteResponse(200, json.dumps({"proposal": proposal,
            "warning": "Todos os efeitos Artístico, Degradê e Suave posteriores serão descartados nesta página."},
            ensure_ascii=False).encode("utf-8"))
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        return RouteResponse(400, json.dumps({"error": str(exc)}, ensure_ascii=False).encode("utf-8"))


def post_response(payload: object, output_root: Path) -> RouteResponse:
    try:
        if not isinstance(payload, dict) or set(payload) != {
                "provider", "manga", "chapter", "page", "proposal", "confirmed"}:
            raise ValueError("Solicitação de restauração inválida.")
        provider, name, chapter, page = (_value(payload, key)
            for key in ("provider", "manga", "chapter", "page"))
        if payload["confirmed"] is not True:
            raise ValueError("Confirmação explícita necessária para restaurar a página.")
        manga = _manga(provider, name, output_root)
        proposal = inspect(manga, provider, chapter, page)
        if (not isinstance(payload["proposal"], dict)
                or proposal_version(payload["proposal"]) != proposal["version"]):
            raise ValueError("Prévia obsoleta: atualize antes de restaurar a página.")
        def operation(progress, _job_id):
            progress(chapter, {"stage": "restore", "percent": 10,
                "message": f"Restaurando {page} em cópia transacional."})
            result = restore(manga, provider, chapter, page, payload["proposal"], confirmed=True)
            progress(chapter, {"stage": "done", "percent": 100,
                "message": f"Página {page} restaurada."})
            return [result]
        job = submit(operation, total=1)
        return RouteResponse(202, json.dumps({"job": job}, ensure_ascii=False).encode("utf-8"))
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        return RouteResponse(400, json.dumps({"error": str(exc)}, ensure_ascii=False).encode("utf-8"))
