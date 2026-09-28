"""Enqueue the selected Level V operation."""
import json
from pathlib import Path

from central_v2.backend.jobs.manager import submit
from central_v2.backend.routes.response import RouteResponse
from central_v2.backend.state.catalog import build_catalog
from central_v2.backend.state.manga_state import resolve_manga
from orquestracao.auto_merge.executar_nivel5 import execute_level5, validate_level5_selection
from orquestracao.central_session import legacy_server_active


def execute_level5_response(payload: object, output_root: Path) -> RouteResponse:
    try:
        if not isinstance(payload, dict):
            raise ValueError("Corpo da solicitação inválido.")
        provider, name, chapters = payload.get("provider"), payload.get("manga"), payload.get("chapters")
        if not isinstance(provider, str) or not isinstance(name, str) or not provider or not name:
            raise ValueError("provider e manga são obrigatórios.")
        manga = resolve_manga(output_root, provider, name)
        if name not in build_catalog(output_root).get(provider, []):
            raise ValueError("Obra fora do catálogo.")
        validate_level5_selection(manga, chapters)
        if legacy_server_active():
            raise ValueError("Feche a Central V1 antes de executar o Auto-Merge na V2.")

        def operation(progress, job_id):
            def preflight():
                if legacy_server_active():
                    raise RuntimeError("Central V1 ativa; execução cancelada por segurança.")
            return execute_level5(manga, chapters, job_id, progress, preflight)

        job = submit(operation, total=len(chapters))
        return RouteResponse(202, json.dumps({"job": job}, ensure_ascii=False,
                                             separators=(",", ":")).encode())
    except ValueError as exc:
        return RouteResponse(400, _error(str(exc)))
    except OSError:
        return RouteResponse(500, _error("Não foi possível iniciar a execução do Nível V."))


def _error(message: str) -> bytes:
    return json.dumps({"error": message}, ensure_ascii=False).encode()
