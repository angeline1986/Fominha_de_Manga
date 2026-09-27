"""HTTP contract for starting one validated Level I selection."""
import json
from pathlib import Path

from central_v2.backend.jobs.manager import submit
from central_v2.backend.routes.response import RouteResponse
from central_v2.backend.state.catalog import build_catalog
from central_v2.backend.state.manga_state import resolve_manga
from orquestracao.auto_merge.executar_nivel1 import execute_level1, validate_selection
from orquestracao.central_session import legacy_server_active


def execute_response(payload: object, output_root: Path) -> RouteResponse:
    try:
        if not isinstance(payload, dict):
            raise ValueError("Corpo da solicitação inválido.")
        provider, name = payload.get("provider"), payload.get("manga")
        chapters = payload.get("chapters")
        if not isinstance(provider, str) or not isinstance(name, str) or not provider or not name:
            raise ValueError("provider e manga são obrigatórios.")
        manga = resolve_manga(output_root, provider, name)
        if name not in build_catalog(output_root).get(provider, []):
            raise ValueError("Obra fora do catálogo.")
        validate_selection(manga, chapters)
        if legacy_server_active():
            raise ValueError("Feche a Central V1 antes de executar o Auto-Merge na V2.")

        def operation(progress, job_id):
            def preflight():
                if legacy_server_active():
                    raise RuntimeError("Central V1 ativa; execução cancelada por segurança.")
            return execute_level1(manga, chapters, job_id, progress, preflight)

        job = submit(operation, total=len(chapters))
        return RouteResponse(202, _json({"job": job}))
    except ValueError as exc:
        return RouteResponse(400, _json({"error": str(exc)}))
    except OSError:
        return RouteResponse(500, _json({"error": "Não foi possível iniciar a execução."}))


def _json(payload: dict) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
