"""Read-only API for chapter-level special treatment worklists."""
import json
from pathlib import Path

from central_v2.backend.jobs.manager import submit
from central_v2.backend.orchestration.textoff_merged.special_degrade_execution import (
    execute_degrade, validate_degrade_chapters, validate_degrade_reexecution,
)
from central_v2.backend.orchestration.textoff_merged.special_smooth_execution import (
    execute_smooth, validate_smooth_reexecution,
)
from central_v2.backend.orchestration.textoff_merged.special_styled_execution import (
    execute_styled, validate_styled_reexecution,
)
from central_v2.backend.orchestration.textoff_merged.special_styled_input import (
    validate_chapters as validate_styled_chapters,
)
from central_v2.backend.orchestration.textoff_merged.special_smooth_input import validate_chapters as validate_smooth_chapters
from central_v2.backend.orchestration.textoff_merged.special_treatments_query import query_special_treatments
from central_v2.backend.routes.response import RouteResponse
from central_v2.backend.state.catalog import build_catalog
from central_v2.backend.state.manga_state import resolve_manga

ROUTE = "/api/textoff/special/treatments"
EXECUTE_ROUTE = ROUTE + "/execute"


def _manga(provider: str, name: str, output_root: Path) -> Path:
    if not provider or not name or name not in build_catalog(output_root).get(provider, []):
        raise ValueError("Obra inválida ou fora do catálogo.")
    return resolve_manga(output_root, provider, name)


def special_treatments_response(query: dict, output_root: Path) -> RouteResponse:
    try:
        provider = (query.get("provider") or [""])[0]
        name = (query.get("manga") or [""])[0]
        treatment = (query.get("treatment") or [""])[0]
        manga = _manga(provider, name, output_root)
        payload = query_special_treatments(manga, provider, treatment)
        return RouteResponse(200, json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        return RouteResponse(400, json.dumps({"error": str(exc)}, ensure_ascii=False).encode("utf-8"))


def execute_special_treatments_response(payload: object, output_root: Path) -> RouteResponse:
    try:
        if (not isinstance(payload, dict) or set(payload) -
                {"provider", "manga", "treatment", "chapters", "retry", "reexecute", "selections"}):
            raise ValueError("Solicitação de tratamento especial inválida.")
        treatment = payload.get("treatment")
        if treatment not in {"degrade", "estilizado", "gradiente_suave"}:
            raise ValueError("Tratamento especial indisponível para execução.")
        retry = payload.get("retry", False)
        reexecute = payload.get("reexecute", False)
        if type(retry) is not bool:
            raise ValueError("Solicitação de nova tentativa inválida.")
        if type(reexecute) is not bool or (retry and reexecute):
            raise ValueError("Solicitação de reexecução inválida.")
        if "selections" in payload and not (treatment == "estilizado" and reexecute):
            raise ValueError("Seleção por ocorrência só é válida na reexecução Artístico.")
        provider, name = payload.get("provider"), payload.get("manga")
        manga = _manga(provider, name, output_root)
        if treatment == "degrade":
            if reexecute:
                chapters = validate_degrade_reexecution(manga, provider, payload.get("chapters"))
            else:
                chapters = validate_degrade_chapters(manga, provider, payload.get("chapters"), retry=retry)
            runner = execute_degrade
        elif treatment == "estilizado":
            if reexecute:
                selections = validate_styled_reexecution(manga, provider,
                    payload.get("chapters"), payload.get("selections"))
                chapters = list(selections)
            else:
                if "selections" in payload:
                    raise ValueError("Seleção de ocorrência é exclusiva da reexecução Artístico.")
                chapters = validate_styled_chapters(manga, provider, payload.get("chapters"), retry=retry)
            runner = execute_styled
        else:
            if reexecute:
                chapters = validate_smooth_reexecution(manga, provider, payload.get("chapters"))
            else:
                chapters = validate_smooth_chapters(manga, provider, payload.get("chapters"), retry=retry)
            runner = execute_smooth
        def operation(progress, _job_id):
            options = {"retry": retry, "reexecute": reexecute}
            if treatment == "estilizado" and reexecute:
                options["selections"] = selections
            return runner(manga, provider, chapters, progress, **options)
        job = submit(operation, total=len(chapters))
        return RouteResponse(202, json.dumps({"job": job}, ensure_ascii=False).encode("utf-8"))
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        return RouteResponse(400, json.dumps({"error": str(exc)}, ensure_ascii=False).encode("utf-8"))
