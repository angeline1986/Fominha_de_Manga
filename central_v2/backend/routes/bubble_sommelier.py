"""BubbleSommelier HTTP contracts."""
import json
from pathlib import Path

from central_v2.backend.jobs.manager import submit
from central_v2.backend.routes.response import RouteResponse
from central_v2.backend.state.catalog import build_catalog
from central_v2.backend.state.manga_state import resolve_manga
from central_v2.backend.orchestration.bubble_sommelier import execute, query, validate_selection


def response(query_values: dict, output_root: Path) -> RouteResponse:
    try:
        provider, name = _context(query_values, output_root)
        manga = resolve_manga(output_root, provider, name)
        return RouteResponse(200, _json({"provider": provider, "manga": name, **query(manga)}))
    except ValueError as exc:
        return RouteResponse(400, _json({"error": str(exc)}))
    except OSError:
        return RouteResponse(500, _json({"error": "Não foi possível consultar o BubbleSommelier."}))


def execute_response(payload: object, output_root: Path) -> RouteResponse:
    try:
        if not isinstance(payload, dict):
            raise ValueError("Corpo da solicitação inválido.")
        provider, name = _context(payload, output_root)
        manga = resolve_manga(output_root, provider, name)
        chapters = validate_selection(manga, payload.get("chapters"))

        def operation(progress, _job_id):
            return execute(manga, chapters, progress)

        return RouteResponse(202, _json({"job": submit(operation, total=len(chapters))}))
    except ValueError as exc:
        return RouteResponse(400, _json({"error": str(exc)}))
    except OSError:
        return RouteResponse(500, _json({"error": "Não foi possível iniciar o BubbleSommelier."}))


def _context(payload: dict, output_root: Path) -> tuple[str, str]:
    provider, name = _value(payload, "provider"), _value(payload, "manga")
    if not isinstance(provider, str) or not provider or not isinstance(name, str) or not name:
        raise ValueError("provider e manga são obrigatórios.")
    if name not in build_catalog(output_root).get(provider, []):
        raise ValueError("Obra fora do catálogo.")
    return provider, name


def _value(payload: dict, key: str):
    value = payload.get(key)
    return value[0] if isinstance(value, list) and value else value


def _json(payload: dict) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
