"""Open a validated Auto-Merge stage folder for a chapter."""
import json
import subprocess
from pathlib import Path

from central_v2.backend.routes.response import RouteResponse
from central_v2.backend.state.manga_state import resolve_manga
from central_v2.backend.state.work_layout import AUTO_MERGE_STAGES, processing_stage_root


def open_auto_merge_folder_response(payload: object, output_root: Path) -> RouteResponse:
    try:
        if not isinstance(payload, dict):
            raise ValueError("Solicitação inválida.")
        provider, manga_name = payload.get("provider"), payload.get("manga")
        chapter, level = payload.get("chapter"), payload.get("level")
        if not all(isinstance(value, str) and value for value in (provider, manga_name, chapter)):
            raise ValueError("Provider, obra e capítulo são obrigatórios.")
        if type(level) is not int or level not in AUTO_MERGE_STAGES:
            raise ValueError("Nível de Auto-Merge inválido.")
        manga = resolve_manga(output_root, provider, manga_name)
        stage_root = processing_stage_root(manga, AUTO_MERGE_STAGES[level]).resolve()
        target = (stage_root / chapter).resolve()
        if target.parent != stage_root or not target.is_dir():
            raise ValueError("Pasta do estágio não encontrada.")
        subprocess.Popen(["open", str(target)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return _response(200, {"ok": True})
    except ValueError as error:
        return _response(400, {"error": str(error)})
    except OSError:
        return _response(500, {"error": "Não foi possível abrir a pasta do Auto-Merge."})


def _response(status: int, payload: dict) -> RouteResponse:
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
    return RouteResponse(status, body)
