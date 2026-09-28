"""HTTP contracts for Balanceamento queries and explicit jobs."""
import json
from pathlib import Path

from central_v2.backend.jobs.manager import submit
from central_v2.backend.routes.response import RouteResponse
from central_v2.backend.state.catalog import build_catalog
from central_v2.backend.state.manga_state import resolve_manga
from orquestracao.balanceamento.fluxo import (
    apply_manual, generate_manual, prepare_manual, read_state, validate_state,
)
from orquestracao.central_session import legacy_server_active


def balanceamento_response(query: dict, output_root: Path) -> RouteResponse:
    try:
        provider, name = _context(query, output_root)
        return RouteResponse(200, _json(read_state(resolve_manga(output_root, provider, name))))
    except ValueError as exc:
        return RouteResponse(400, _json({"error": str(exc)}))
    except OSError:
        return RouteResponse(500, _json({"error": "Não foi possível consultar o Balanceamento."}))


def balanceamento_job_response(action: str, payload: object, output_root: Path) -> RouteResponse:
    try:
        if not isinstance(payload, dict):
            raise ValueError("Corpo da solicitação inválido.")
        provider, name = _context(payload, output_root)
        manga = resolve_manga(output_root, provider, name)
        chapter, files, cuts = _selection(payload, action)
        if legacy_server_active():
            raise ValueError("Feche a Central V1 antes de executar o Balanceamento na V2.")

        def operation(update, job_id):
            if legacy_server_active():
                raise RuntimeError("Central V1 ativa; operação de Balanceamento cancelada por segurança.")
            notify = lambda message: update(chapter or "Obra", {
                "percent": 40, "stage": action, "message": message, "completed": 0, "total": 1,
            })
            if action == "validate":
                result = validate_state(manga, notify)
            elif action == "prepare":
                result = prepare_manual(manga, chapter, files, notify)
            elif action == "proposal":
                result = generate_manual(manga, chapter, files, cuts, notify)
            else:
                result = apply_manual(manga, chapter, notify)
            update(chapter or "Obra", {
                "percent": 100, "stage": action, "message": "Operação concluída.", "completed": 1, "total": 1,
            })
            return [{"chapter": chapter, "status": "ok", "data": result}]

        return RouteResponse(202, _json({"job": submit(operation, total=1)}))
    except ValueError as exc:
        return RouteResponse(400, _json({"error": str(exc)}))
    except OSError:
        return RouteResponse(500, _json({"error": "Não foi possível iniciar o job de Balanceamento."}))


def _selection(payload: dict, action: str):
    if action == "validate":
        return "", [], []
    chapter = str(payload.get("chapter") or "")
    files = payload.get("merges")
    if not chapter or chapter in {".", ".."} or Path(chapter).name != chapter or "/" in chapter or "\\" in chapter:
        raise ValueError("Capítulo inválido.")
    if not isinstance(files, list) or not all(isinstance(name, str) and Path(name).name == name for name in files):
        raise ValueError("A seleção de merges é inválida.")
    if action in {"prepare", "proposal"} and len(files) < 2:
        raise ValueError("Selecione pelo menos dois merges contíguos.")
    cuts = payload.get("cuts") or []
    if action == "proposal" and (not isinstance(cuts, list) or any(type(cut) is not int for cut in cuts)):
        raise ValueError("A lista de cortes é inválida.")
    return chapter, files, cuts


def _context(payload: dict, output_root: Path) -> tuple[str, str]:
    def value(key: str):
        item = payload.get(key)
        return item[0] if isinstance(item, list) and item else item

    provider, name = value("provider"), value("manga")
    if not isinstance(provider, str) or not provider or not isinstance(name, str) or not name:
        raise ValueError("provider e manga são obrigatórios.")
    if name not in build_catalog(output_root).get(provider, []):
        raise ValueError("Obra fora do catálogo.")
    return provider, name


def _json(payload: dict) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
