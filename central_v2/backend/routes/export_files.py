"""Central V2 HTTP adapter for the existing export domain."""
import json
from pathlib import Path

from central_v2.backend.routes.response import RouteResponse
from central_v2.backend.state.manga_state import resolve_manga
from processamento.exportacao.exportador import execute_plan, list_source_files, select_directory, simulate_export


def _reply(status, data):
    return RouteResponse(status, json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode())


def directory_response():
    try:
        return _reply(200, select_directory())
    except (ValueError, RuntimeError, OSError) as exc:
        return _reply(400, {"error": str(exc)})


def export_response(action: str, payload: object, output_root: Path):
    try:
        if not isinstance(payload, dict):
            raise ValueError("Solicitação inválida.")
        provider, name = payload.get("provider"), payload.get("manga")
        if not isinstance(provider, str) or not isinstance(name, str):
            raise ValueError("Selecione uma obra válida.")
        manga = resolve_manga(output_root, provider, name)
        if action == "files":
            kind=payload.get("kind")
            if not isinstance(kind,str): raise ValueError("Conteúdo inválido.")
            data=list_source_files(manga,kind)
        elif action == "simulate":
            dest = payload.get("destination")
            keys = payload.get("contents")
            if not isinstance(dest, str) or not isinstance(keys, list) or not all(isinstance(k, str) for k in keys):
                raise ValueError("Destino ou conteúdos inválidos.")
            data = simulate_export(manga, dest, keys, payload.get("file_selection"))
        elif action == "execute":
            plan_id = payload.get("plan_id")
            if not isinstance(plan_id, str) or not plan_id:
                raise ValueError("Simule a exportação antes de executar.")
            data = execute_plan(manga, plan_id)
        else:
            return _reply(404, {"error": "Ação desconhecida."})
        return _reply(200, data)
    except (ValueError, OSError) as exc:
        return _reply(400, {"error": str(exc)})
