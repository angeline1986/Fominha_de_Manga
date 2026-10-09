"""GET and POST endpoints for page-scoped TextOff residue cataloging."""
import json
from pathlib import Path

from PIL import Image

from config.data_paths import OUTPUT_ROOT
from central_v2.backend.orchestration.textoff_merged.comparison import comparison_pairs
from central_v2.backend.orchestration.textoff_merged.residue_occurrences import (
    MANIFEST_NAME, occurrences_for, read_manifest, update_page, update_pages,
    validate_occurrences,
)
from central_v2.backend.orchestration.textoff_merged.auto_cleaner_check import (
    StaleCheckSourcesError, load_check_page, save_check_decision,
)
from central_v2.backend.orchestration.textoff_merged.stages import stage_chapter
from central_v2.backend.routes.auto_cleaner_check_special_treatments import rebuild_after_check
from central_v2.backend.routes.response import RouteResponse
from central_v2.backend.state.manga_state import resolve_manga

ROUTE = "/api/textoff/residue-occurrences"


def residue_occurrences_get_response(query: dict, output_root: Path = OUTPUT_ROOT) -> RouteResponse:
    try:
        context, manga, pair, page, step = _resolve_context(query, output_root)
        if (query.get("scope") or [None])[0] == "check":
            result = load_check_page(
                manga, _document(context), context["capitulo"], page,
                comparison_pairs(manga, context["capitulo"], step),
            )
            return _json_response(200, result)
        path = _manifest_path(manga, context["capitulo"])
        manifest = read_manifest(path, _document(context))
        rows = []
        for row in occurrences_for(manifest, page, step):
            origin = row.get("origin")
            if origin not in {"MAPEAR", "SOMMELIER", "MANUAL"}:
                origin = "MANUAL"
            rows.append({**row, "origin": origin,
                         "origins": row.get("origins", [origin])})
        return _json_response(200, {"page": page, "step": step, "occurrences": rows,
                                    "cataloged": bool(rows)})
    except (ValueError, TypeError) as exc:
        return _json_response(400, {"error": str(exc)})
    except OSError:
        return _json_response(500, {"error": "Não foi possível carregar as ocorrências."})


def residue_occurrences_post_response(payload: object, output_root: Path = OUTPUT_ROOT) -> RouteResponse:
    try:
        if not isinstance(payload, dict):
            raise ValueError("Payload de catalogação inválido.")
        if payload.get("scope") == "check":
            return _check_batch_post_response(payload, output_root)
        if "pages" in payload:
            return _batch_post_response(payload, output_root)
        context, manga, pair, page, step = _resolve_context(payload, output_root)
        with Image.open(pair["after"]) as image:
            natural_width, natural_height = image.size
        occurrences = validate_occurrences(payload.get("occurrences"), natural_width, natural_height)
        path = _manifest_path(manga, context["capitulo"])
        update_page(path, _document(context), page, step, occurrences)
        return _json_response(200, {"ok": True, "page": page, "step": step,
                                    "occurrences": occurrences, "total_occurrences": len(occurrences)})
    except (ValueError, TypeError) as exc:
        return _json_response(400, {"error": str(exc)})
    except OSError:
        return _json_response(500, {"error": "Não foi possível persistir as ocorrências."})


def _check_batch_post_response(payload: dict, output_root: Path) -> RouteResponse:
    context, manga, pairs, step = _resolve_catalog_context(payload, output_root)
    if step != "1":
        raise ValueError("O Auto-Cleaner Check exige a imagem-base do Passo 1.")
    raw_pages = payload.get("pages")
    if not isinstance(raw_pages, list) or not raw_pages:
        raise ValueError("O lote do Check precisa conter ao menos uma página.")
    pair_by_name = {pair["name"]: pair for pair in pairs}
    validated, names = [], set()
    for item in raw_pages:
        if not isinstance(item, dict):
            raise ValueError("Página do lote do Check inválida.")
        page = _required(item, "page")
        _validate_page_name(page)
        if page in names or page not in pair_by_name:
            raise ValueError("Página repetida ou fora da comparação selecionada.")
        names.add(page)
        with Image.open(pair_by_name[page]["after"]) as image:
            occurrences = validate_occurrences(
                item.get("occurrences"), image.width, image.height,
                allow_unclassified=True,
            )
        validated.append((page, [dict(row, page=page) for row in occurrences]))
    try:
        manifest = save_check_decision(
            manga, _document(context), context["capitulo"], validated, pairs,
            payload.get("source_snapshot"),
        )
    except StaleCheckSourcesError as exc:
        return _json_response(409, {"error": str(exc), "stale_sources": True})
    failure = rebuild_after_check(manga, _document(context), context["capitulo"])
    if failure:
        return failure
    results = [{"page": page, "occurrences": rows, "total_occurrences": len(rows)}
               for page, rows in validated]
    return _json_response(200, {
        "ok": True, "scope": "check", "decision_persisted": True,
        "special_treatments_updated": True,
        "pages": results, "updated_at": manifest["updated_at"],
    })


def _batch_post_response(payload: dict, output_root: Path) -> RouteResponse:
    if "page" in payload:
        raise ValueError("Informe page ou pages, não ambos.")
    context, manga, pairs, step = _resolve_catalog_context(payload, output_root)
    raw_pages = payload.get("pages")
    if not isinstance(raw_pages, list) or not raw_pages:
        raise ValueError("O lote precisa conter ao menos uma página.")
    pair_by_name = {pair["name"]: pair for pair in pairs}
    validated, names = [], set()
    for item in raw_pages:
        if not isinstance(item, dict):
            raise ValueError("Página do lote inválida.")
        page = _required(item, "page")
        _validate_page_name(page)
        if page in names or page not in pair_by_name:
            raise ValueError("Página repetida ou fora da comparação selecionada.")
        names.add(page)
        with Image.open(pair_by_name[page]["after"]) as image:
            occurrences = validate_occurrences(
                item.get("occurrences"), image.width, image.height,
            )
        validated.append((page, occurrences))
    path = _manifest_path(manga, context["capitulo"])
    manifest = update_pages(path, _document(context), step, validated)
    results = [{"page": page, "occurrences": occurrences,
                "total_occurrences": len(occurrences)} for page, occurrences in validated]
    return _json_response(200, {"ok": True, "step": step, "pages": results,
                                "updated_at": manifest["meta"]["atualizado_em"]})


def _resolve_context(values: dict, output_root: Path):
    context, manga, pairs, step = _resolve_catalog_context(values, output_root)
    page = _required(values, "page")
    _validate_page_name(page)
    pair = next((item for item in pairs if item.get("name") == page), None)
    if pair is None:
        raise ValueError("A página não pertence à comparação selecionada.")
    return context, manga, pair, page, step


def _resolve_catalog_context(values: dict, output_root: Path):
    provider = _required(values, "provider")
    name = _required(values, "manga")
    chapter = _required(values, "chapter")
    step = _required(values, "step")
    if step not in {"1", "2", "3", "4"}:
        raise ValueError("Passo de comparação inválido.")
    if Path(chapter).name != chapter or chapter in {".", ".."} or "\\" in chapter:
        raise ValueError("Capitulo invalido.")
    manga = resolve_manga(output_root, provider, name)
    pairs = comparison_pairs(manga, chapter, step)
    return {"provider": provider, "obra": name, "capitulo": chapter}, manga, pairs, step


def _validate_page_name(page: str) -> None:
    if (Path(page).name != page or page in {".", ".."} or Path(page).is_absolute()
            or "\\" in page):
        raise ValueError("Nome de página inválido.")


def _manifest_path(manga: Path, chapter: str) -> Path:
    root = manga.resolve()
    folder = stage_chapter(manga, "RESIDUE_OCCURRENCES", chapter, read_legacy=False).resolve()
    if not folder.is_relative_to(root):
        raise ValueError("Destino do manifesto fora da obra autorizada.")
    target = folder / MANIFEST_NAME
    if not target.resolve().is_relative_to(folder):
        raise ValueError("Manifesto fora do diretório de auditoria autorizado.")
    return target


def _document(context: dict) -> dict:
    return {"provider": context["provider"], "obra": context["obra"], "capitulo": context["capitulo"]}


def _required(values: dict, key: str) -> str:
    value = values.get(key)
    if isinstance(value, list):
        value = value[0] if value else None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"O campo {key} é obrigatório.")
    return value.strip()


def _json_response(status: int, payload: dict) -> RouteResponse:
    return RouteResponse(status, json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
