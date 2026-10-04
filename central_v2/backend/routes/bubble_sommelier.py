"""BubbleSommelier HTTP contracts."""
import json
from pathlib import Path

from central_v2.backend.jobs.manager import submit
from central_v2.backend.routes.response import RouteResponse
from central_v2.backend.state.catalog import build_catalog
from central_v2.backend.state.manga_state import resolve_manga
from central_v2.backend.orchestration.bubble_sommelier import (
    execute, query, validate_profile_id, validate_selection,
)
from central_v2.backend.orchestration.bubble_sommelier.artifacts import (
    crop_path, crop_sha256, load_review_report, validate_chapter_id,
    validate_crop_identity,
)


def response(query_values: dict, output_root: Path) -> RouteResponse:
    try:
        provider, name = _context(query_values, output_root)
        manga = resolve_manga(output_root, provider, name)
        return RouteResponse(200, _json({"provider": provider, "manga": name, **query(manga)}))
    except ValueError as exc:
        return RouteResponse(400, _json({"error": str(exc)}))
    except OSError:
        return RouteResponse(500, _json({"error": "Não foi possível consultar o BubbleSommelier."}))


def execute_response(payload: object, output_root: Path) -> RouteResponse:
    try:
        if not isinstance(payload, dict):
            raise ValueError("Corpo da solicitação inválido.")
        provider, name = _context(payload, output_root)
        manga = resolve_manga(output_root, provider, name)
        chapters = validate_selection(manga, payload.get("chapters"))
        profile_id = validate_profile_id(payload.get("profile_id"))

        def operation(progress, _job_id):
            return execute(manga, chapters, progress, profile_id=profile_id)

        return RouteResponse(202, _json({"job": submit(operation, total=len(chapters))}))
    except ValueError as exc:
        return RouteResponse(400, _json({"error": str(exc)}))
    except OSError:
        return RouteResponse(500, _json({"error": "Não foi possível iniciar o BubbleSommelier."}))


def review_response(query_values: dict, output_root: Path) -> RouteResponse:
    try:
        provider, name = _context(query_values, output_root)
        manga = resolve_manga(output_root, provider, name)
        chapter = validate_chapter_id(_required(query_values, "chapter"))
        report = load_review_report(manga, chapter)
        result = report["checkpoints"]["result"]
        pages = []
        for page in report["pages"]:
            pages.append({
                "page_id": page["page_id"],
                "bubbles": [_review_bubble(bubble) for bubble in page["bubbles"]],
            })
        return RouteResponse(200, _json({
            "chapter": chapter,
            "profile_id": report["profile_id"],
            "summary": {
                "balloons": result["crops"],
                "candidates": result["candidates"],
                "coverage_ge_075": result["coverageGe075"],
            },
            "pages": pages,
        }))
    except ValueError as exc:
        return RouteResponse(400, _json({"error": str(exc)}))
    except FileNotFoundError as exc:
        return RouteResponse(404, _json({"error": str(exc)}))
    except RuntimeError as exc:
        return RouteResponse(422, _json({"error": str(exc)}))
    except OSError:
        return RouteResponse(500, _json({"error": "Não foi possível ler a revisão do BubbleSommelier."}))


def crop_response(query_values: dict, output_root: Path) -> RouteResponse:
    try:
        provider, name = _context(query_values, output_root)
        manga = resolve_manga(output_root, provider, name)
        chapter = validate_chapter_id(_required(query_values, "chapter"))
        identity = validate_crop_identity(_required(query_values, "identity"))
        report = load_review_report(manga, chapter)
        bubble = next(
            (bubble for page in report["pages"] for bubble in page["bubbles"]
             if bubble["identity"] == identity),
            None,
        )
        if bubble is None:
            raise FileNotFoundError(f"Identity não pertence ao capítulo {chapter}: {identity}")

        path = crop_path(manga, chapter, identity)
        if crop_sha256(path) != bubble["crop"]["sha256"]:
            return RouteResponse(409, _json({"error": "SHA-256 do crop diverge do report."}))
        return RouteResponse(200, path.read_bytes(), "image/png")
    except ValueError as exc:
        return RouteResponse(400, _json({"error": str(exc)}))
    except FileNotFoundError as exc:
        return RouteResponse(404, _json({"error": str(exc)}))
    except RuntimeError as exc:
        return RouteResponse(422, _json({"error": str(exc)}))
    except OSError:
        return RouteResponse(500, _json({"error": "Não foi possível ler o crop do BubbleSommelier."}))


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


def _required(payload: dict, key: str) -> str:
    value = _value(payload, key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} é obrigatório.")
    return value


def _review_bubble(bubble: dict) -> dict:
    fields = ("identity", "bubble_index", "confidence", "bbox", "crop", "metrics", "candidate")
    return {field: bubble[field] for field in fields if field in bubble}


def _json(payload: dict) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
