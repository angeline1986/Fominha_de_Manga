"""Read-only API for chapter-level special treatment worklists."""
import json
from pathlib import Path

from central_v2.backend.orchestration.textoff_merged.special_treatments_query import query_special_treatments
from central_v2.backend.routes.response import RouteResponse
from central_v2.backend.state.catalog import build_catalog
from central_v2.backend.state.manga_state import resolve_manga

ROUTE = "/api/textoff/special/treatments"


def special_treatments_response(query: dict, output_root: Path) -> RouteResponse:
    try:
        provider = (query.get("provider") or [""])[0]
        name = (query.get("manga") or [""])[0]
        treatment = (query.get("treatment") or [""])[0]
        if not provider or not name or name not in build_catalog(output_root).get(provider, []):
            raise ValueError("Obra inválida ou fora do catálogo.")
        manga = resolve_manga(output_root, provider, name)
        payload = query_special_treatments(manga, provider, treatment)
        return RouteResponse(200, json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        return RouteResponse(400, json.dumps({"error": str(exc)}, ensure_ascii=False).encode("utf-8"))
