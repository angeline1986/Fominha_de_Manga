"""HTTP contracts for the TextOff Merged worklist and Cleaner V2 jobs."""
import json
from pathlib import Path

from central_v2.backend.jobs.manager import submit
from central_v2.backend.routes.response import RouteResponse
from central_v2.backend.state.catalog import build_catalog
from central_v2.backend.state.manga_state import resolve_manga
from orquestracao.central_session import legacy_server_active
from central_v2.backend.orchestration.textoff_merged import (
    execute_merged, execute_merged_level1, execute_merged_level2, query_merged,
    query_merged_level1, query_merged_level2, validate_level2_selection,
    validate_selection,
)


def textoff_merged_response(query: dict, output_root: Path) -> RouteResponse:
    try:
        provider, name = _context(query, output_root)
        manga = resolve_manga(output_root, provider, name)
        return RouteResponse(200, _json({"provider": provider, "manga": name, **query_merged(manga)}))
    except ValueError as exc:
        return RouteResponse(400, _json({"error": str(exc)}))
    except OSError:
        return RouteResponse(500, _json({"error": "Não foi possível consultar TextOff Merged."}))


def textoff_merged_level_response(level: str, query: dict, output_root: Path) -> RouteResponse:
    try:
        provider, name = _context(query, output_root)
        manga = resolve_manga(output_root, provider, name)
        lookup = {"I": query_merged_level1, "II": query_merged_level2}.get(level)
        if lookup is None:
            raise ValueError("Nível Merged inválido.")
        return RouteResponse(200, _json({"provider": provider, "manga": name, **lookup(manga)}))
    except ValueError as exc:
        return RouteResponse(400, _json({"error": str(exc)}))
    except OSError:
        return RouteResponse(500, _json({"error": "Não foi possível consultar o nível Merged."}))


def execute_textoff_merged_response(payload: object, output_root: Path) -> RouteResponse:
    return _execute_response(payload, output_root, execute_merged)


def execute_textoff_merged_level1_response(payload: object, output_root: Path) -> RouteResponse:
    return _execute_response(payload, output_root, execute_merged_level1)


def execute_textoff_merged_level2_response(payload: object, output_root: Path) -> RouteResponse:
    return _execute_response(payload, output_root, execute_merged_level2, validate_level2_selection)


def _execute_response(payload: object, output_root: Path, runner, validator=None) -> RouteResponse:
    try:
        if not isinstance(payload, dict):
            raise ValueError("Corpo da solicitação inválido.")
        provider, name = _context(payload, output_root)
        manga = resolve_manga(output_root, provider, name)
        chapters = (validator or validate_selection)(manga, payload.get("chapters"))
        if legacy_server_active():
            raise ValueError("Feche a Central V1 antes de executar TextOff na V2.")

        def operation(progress, job_id):
            if legacy_server_active():
                raise RuntimeError("Central V1 ativa; execução TextOff cancelada por segurança.")
            return runner(
                manga,
                chapters,
                progress,
                preflight=lambda: _ensure_v2_session(),
            )

        return RouteResponse(202, _json({"job": submit(operation, total=len(chapters))}))
    except ValueError as exc:
        return RouteResponse(400, _json({"error": str(exc)}))
    except OSError:
        return RouteResponse(500, _json({"error": "Não foi possível iniciar TextOff Merged."}))


def _ensure_v2_session():
    if legacy_server_active():
        raise RuntimeError("Central V1 ativa; execução TextOff cancelada por segurança.")


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
