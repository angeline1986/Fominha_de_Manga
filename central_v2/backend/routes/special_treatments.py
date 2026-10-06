"""Read-only API for chapter-level special treatment worklists."""
import json
from pathlib import Path

from central_v2.backend.jobs.manager import submit
from central_v2.backend.orchestration.textoff_merged.special_degrade_execution import (
    execute_degrade, validate_degrade_chapters,
)
from central_v2.backend.orchestration.textoff_merged.special_treatments_query import query_special_treatments
from central_v2.backend.routes.response import RouteResponse
from central_v2.backend.state.catalog import build_catalog
from central_v2.backend.state.manga_state import resolve_manga

ROUTE = "/api/textoff/special/treatments"
EXECUTE_ROUTE = ROUTE + "/execute"


def _manga(provider: str, name: str, output_root: Path) -> Path:
    if not provider or not name or name not in build_catalog(output_root).get(provider, []):
        raise ValueError("Obra inválida ou fora do catálogo.")
    return resolve_manga(output_root, provider, name)


def special_treatments_response(query: dict, output_root: Path) -> RouteResponse:
    try:
        provider = (query.get("provider") or [""])[0]
        name = (query.get("manga") or [""])[0]
        treatment = (query.get("treatment") or [""])[0]
        manga = _manga(provider, name, output_root)
        payload = query_special_treatments(manga, provider, treatment)
        return RouteResponse(200, json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        return RouteResponse(400, json.dumps({"error": str(exc)}, ensure_ascii=False).encode("utf-8"))


def execute_special_treatments_response(payload: object, output_root: Path) -> RouteResponse:
    try:
        if (not isinstance(payload, dict) or set(payload) -
                {"provider", "manga", "treatment", "chapters", "retry"}):
            raise ValueError("Solicitação de tratamento especial inválida.")
        if payload.get("treatment") != "degrade":
            raise ValueError("Somente Degradê está disponível para execução.")
        retry = payload.get("retry", False)
        if type(retry) is not bool:
            raise ValueError("Solicitação de nova tentativa inválida.")
        provider, name = payload.get("provider"), payload.get("manga")
        manga = _manga(provider, name, output_root)
        chapters = validate_degrade_chapters(manga, provider, payload.get("chapters"), retry=retry)
        def operation(progress, _job_id):
            return execute_degrade(manga, provider, chapters, progress, retry=retry)
        job = submit(operation, total=len(chapters))
        return RouteResponse(202, json.dumps({"job": job}, ensure_ascii=False).encode("utf-8"))
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        return RouteResponse(400, json.dumps({"error": str(exc)}, ensure_ascii=False).encode("utf-8"))
