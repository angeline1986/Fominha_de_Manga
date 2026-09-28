"""Expose validated Level IV residuals for the final automatic merge stage."""
import json
from pathlib import Path

from central_v2.backend.routes.response import RouteResponse
from central_v2.backend.state.catalog import build_catalog
from central_v2.backend.state.manga_state import build_structural_state, resolve_manga
from orquestracao.auto_merge.consulta_nivel5 import query_level5


def level5_response(query: dict, output_root: Path) -> RouteResponse:
    provider, name = (query.get("provider") or [""])[0], (query.get("manga") or [""])[0]
    try:
        if not provider or not name:
            raise ValueError("provider e manga são obrigatórios")
        manga = resolve_manga(output_root, provider, name)
        if name not in build_catalog(output_root).get(provider, []):
            raise ValueError("Obra fora do catálogo.")
        context = build_structural_state(output_root, provider, name)
        payload = {"provider": provider, "manga": name,
                   "chapters": query_level5(manga, context["chapters"])}
        status = 200
    except ValueError as exc:
        payload, status = {"error": str(exc)}, 400
    except OSError:
        payload, status = {"error": "Não foi possível consultar os resíduos do Nível V."}, 500
    return RouteResponse(status, json.dumps(payload, ensure_ascii=False).encode("utf-8"))
