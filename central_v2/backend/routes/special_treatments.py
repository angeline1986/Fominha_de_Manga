"""HTTP contracts for special treatment worklists, previews, and execution."""
import json
import hashlib
import mimetypes
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
from central_v2.backend.orchestration.textoff_merged.final_consolidated import read_final_page
from central_v2.backend.routes.response import RouteResponse
from central_v2.backend.state.catalog import build_catalog
from central_v2.backend.state.manga_state import resolve_manga

ROUTE = "/api/textoff/special/treatments"
EXECUTE_ROUTE = ROUTE + "/execute"
IMAGE_ROUTE = ROUTE + "/image"


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


def styled_preview_image_response(query: dict, output_root: Path) -> RouteResponse:
    try:
        provider = (query.get("provider") or [""])[0]
        name = (query.get("manga") or [""])[0]
        chapter = (query.get("chapter") or [""])[0]
        page = (query.get("page") or [""])[0]
        expected = (query.get("sha256") or [""])[0]
        identity = (query.get("id") or [""])[0]
        manga = _manga(provider, name, output_root)
        if not chapter or Path(chapter).name != chapter or not page or Path(page).name != page:
            raise ValueError("Página de tratamento inválida.")
        from central_v2.backend.orchestration.textoff_merged.special_treatments_manifest import manifest_path
        from central_v2.backend.orchestration.textoff_merged.special_styled_source import detection_input
        manifest = json.loads(manifest_path(manga, chapter).read_text(encoding="utf-8"))
        rows = [row for bucket in (manifest.get("treatments") or {}).values()
                if isinstance(bucket, list) for row in bucket
                if row.get("id") == identity and row.get("page") == page]
        if len(rows) != 1:
            raise ValueError("Ocorrência Artístico ausente.")
        row = rows[0]
        if row.get("treatment") == "estilizado" and row.get("status") in {"pending", "failed"}:
            source = detection_input(manga, provider, chapter, page, identity,
                                     row.get("box_pixels"))
            image = Path(source["path"])
        elif row.get("status") in {"pending", "failed", "processed", "no_change"}:
            _record, image, _digest = read_final_page(manga, chapter, page)
        else:
            raise ValueError("Estado Artístico inválido.")
        content = image.read_bytes()
        if hashlib.sha256(content).hexdigest() != expected:
            raise ValueError("Imagem de tratamento mudou desde a consulta.")
        return RouteResponse(200, content,
                             mimetypes.guess_type(image.name)[0] or "image/png")
    except (ValueError, OSError, TypeError, KeyError):
        return RouteResponse(404, json.dumps({"error": "Prévia do tratamento indisponível."}).encode("utf-8"))


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
        if "selections" in payload and treatment != "estilizado":
            raise ValueError("Seleção por ocorrência só é válida em Artístico.")
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
                selections = (_styled_new_selections(payload.get("chapters"), payload["selections"])
                              if "selections" in payload else None)
                chapters = validate_styled_chapters(manga, provider, payload.get("chapters"),
                    retry=retry, selections=selections)
            runner = execute_styled
        else:
            if reexecute:
                chapters = validate_smooth_reexecution(manga, provider, payload.get("chapters"))
            else:
                chapters = validate_smooth_chapters(manga, provider, payload.get("chapters"), retry=retry)
            runner = execute_smooth
        def operation(progress, _job_id):
            options = {"retry": retry, "reexecute": reexecute}
            if treatment == "estilizado" and selections is not None:
                options["selections"] = selections
            return runner(manga, provider, chapters, progress, **options)
        job = submit(operation, total=len(chapters))
        return RouteResponse(202, json.dumps({"job": job}, ensure_ascii=False).encode("utf-8"))
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        return RouteResponse(400, json.dumps({"error": str(exc)}, ensure_ascii=False).encode("utf-8"))


def _styled_new_selections(chapters, raw):
    if (not isinstance(chapters, list) or not chapters
            or any(not isinstance(chapter, str) or not chapter for chapter in chapters)
            or not isinstance(raw, list) or not raw
            or any(not isinstance(item, dict) or set(item) != {"chapter", "page", "id"}
                   or any(not isinstance(item[key], str) or not item[key]
                          for key in ("chapter", "page", "id")) for item in raw)):
        raise ValueError("Seleção de ocorrências Artístico inválida.")
    selected = {chapter: set() for chapter in chapters}
    if len(selected) != len(chapters):
        raise ValueError("Capítulos Artístico duplicados.")
    for item in raw:
        chapter, page, identity = item["chapter"], item["page"], item["id"]
        if chapter not in selected or (page, identity) in selected[chapter]:
            raise ValueError("Ocorrência Artístico duplicada ou fora dos capítulos selecionados.")
        selected[chapter].add((page, identity))
    if any(not rows for rows in selected.values()):
        raise ValueError("Cada capítulo precisa de uma ocorrência Artístico selecionada.")
    return selected
