"""GET and POST endpoints for page-scoped TextOff residue cataloging."""
import json
from pathlib import Path

from PIL import Image

from config.data_paths import OUTPUT_ROOT
from central_v2.backend.orchestration.textoff_merged.comparison import comparison_pairs
from central_v2.backend.orchestration.textoff_merged.residue_occurrences import (
    MANIFEST_NAME, occurrences_for, read_manifest, update_page, validate_occurrences,
)
from central_v2.backend.orchestration.textoff_merged.stages import stage_chapter
from central_v2.backend.routes.response import RouteResponse
from central_v2.backend.state.manga_state import resolve_manga

ROUTE = "/api/textoff/residue-occurrences"


def residue_occurrences_get_response(query: dict, output_root: Path = OUTPUT_ROOT) -> RouteResponse:
    try:
        context, manga, pair, page, step = _resolve_context(query, output_root)
        path = _manifest_path(manga, context["capitulo"])
        manifest = read_manifest(path, _document(context))
        rows = occurrences_for(manifest, page, step)
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


def _resolve_context(values: dict, output_root: Path):
    provider = _required(values, "provider")
    name = _required(values, "manga")
    chapter = _required(values, "chapter")
    page = _required(values, "page")
    step = _required(values, "step")
    if step not in {"1", "2", "3", "4"}:
        raise ValueError("Passo de comparação inválido.")
    if Path(chapter).name != chapter or chapter in {".", ".."} or "\\" in chapter:
        raise ValueError("Capitulo invalido.")
    if (Path(page).name != page or page in {".", ".."} or Path(page).is_absolute()
            or "\\" in page):
        raise ValueError("Nome de página inválido.")
    manga = resolve_manga(output_root, provider, name)
    pairs = comparison_pairs(manga, chapter, step)
    pair = next((item for item in pairs if item.get("name") == page), None)
    if pair is None:
        raise ValueError("A página não pertence à comparação selecionada.")
    return {"provider": provider, "obra": name, "capitulo": chapter}, manga, pair, page, step


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
