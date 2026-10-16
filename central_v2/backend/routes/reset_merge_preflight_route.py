"""Read-only inspection route. No write endpoint is provided."""
import json
from pathlib import Path
from urllib.parse import parse_qs
from central_v2.backend.routes.response import RouteResponse
from central_v2.backend.state.manga_state import resolve_manga
from central_v2.backend.orchestration.textoff_merged.reset_check_override import inspect

ROUTE = "/api/textoff/check/reset-merge/preflight"


def response(query: str, output_root: Path) -> RouteResponse:
    try:
        values = parse_qs(query, keep_blank_values=True)
        def one(name):
            candidates = values.get(name)
            if not candidates or len(candidates) != 1 or not candidates[0]:
                raise ValueError(f"Parâmetro inválido: {name}.")
            return candidates[0]
        provider, manga_name = one("provider"), one("manga")
        manga = resolve_manga(output_root, provider, manga_name)
        payload = inspect(manga, one("chapter"), one("page"))
        return RouteResponse(200, json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    except (ValueError, TypeError, KeyError, OSError, json.JSONDecodeError) as exc:
        return RouteResponse(400, json.dumps({"error": str(exc)}, ensure_ascii=False).encode("utf-8"))
