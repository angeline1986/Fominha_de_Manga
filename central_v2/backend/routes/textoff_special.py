"""HTTP contracts for manual ROI TextOff special levels."""
import json
import mimetypes
from pathlib import Path
from urllib.parse import parse_qs

from central_v2.backend.jobs.manager import submit
from central_v2.backend.orchestration.textoff_merged.manual_specials import (
    TREATMENTS, query_manual_special, resolve_manual_page, run_manual_special,
)
from central_v2.backend.orchestration.textoff_special.artifacts import read_json, sha256
from central_v2.backend.orchestration.textoff_special.catalog import STAGING_ROOT
from central_v2.backend.routes.response import RouteResponse
from central_v2.backend.state.catalog import build_catalog
from central_v2.backend.state.manga_state import resolve_manga


def special_level_response(level: str, query: dict, output_root: Path) -> RouteResponse:
    try:
        manga = _manga(query, output_root)
        if level not in TREATMENTS:
            raise ValueError("Nível especial inválido.")
        return _json_response({**query_manual_special(manga, level), "level": level})
    except ValueError as exc:
        return _json_response({"error": str(exc)}, 400)


def special_image_response(query: dict, output_root: Path) -> RouteResponse:
    try:
        manga = _manga(query, output_root)
        chapter, filename = _value(query, "chapter"), _value(query, "file")
        if not chapter or Path(chapter).name != chapter or Path(filename).name != filename:
            raise ValueError("Imagem inválida.")
        image = resolve_manual_page(manga, chapter, filename)
        return RouteResponse(200, image.read_bytes(),
                             mimetypes.guess_type(image.name)[0] or "image/png")
    except (ValueError, OSError):
        return _json_response({"error": "Imagem de Nível I não encontrada."}, 404)


def special_result_response(query: dict) -> RouteResponse:
    run_id = _value(query, "run_id")
    if not run_id.isalnum():
        return _json_response({"error": "Prévia não encontrada."}, 404)
    folder = (STAGING_ROOT / run_id).resolve()
    if not folder.is_relative_to(STAGING_ROOT.resolve()):
        return _json_response({"error": "Prévia não encontrada."}, 404)
    try:
        manifest = read_json(folder / "manifest.json")
        if manifest.get("execution_status") != "succeeded":
            return _json_response({"error": "Prévia não concluída."}, 404)
        result = (folder / str(manifest.get("result_file") or "")).resolve()
        allowed = {".png", ".jpg", ".jpeg", ".webp"}
        expected = (manifest.get("validation") or {}).get("result_sha256")
        if (not result.is_relative_to(folder) or result.suffix.lower() not in allowed
                or not result.is_file() or not expected or sha256(result) != expected):
            return _json_response({"error": "Imagem da prévia ausente."}, 404)
        return RouteResponse(200, result.read_bytes(),
                             mimetypes.guess_type(result.name)[0] or "image/png")
    except (OSError, ValueError, TypeError):
        return _json_response({"error": "Prévia não encontrada."}, 404)


def execute_special_response(level: str, payload: object, output_root: Path) -> RouteResponse:
    try:
        if not isinstance(payload, dict) or level not in TREATMENTS:
            raise ValueError("Solicitação de tratamento especial inválida.")
        manga = _manga(payload, output_root)
        chapter, filename = payload.get("chapter"), payload.get("filename")
        selections = payload.get("selections")
        if not isinstance(chapter, str) or not isinstance(filename, str):
            raise ValueError("Capítulo e imagem são obrigatórios.")
        def operation(progress, _job_id):
            result = run_manual_special(manga, level, chapter, filename, selections)
            progress(chapter, {"stage": level.lower(), "percent": 100,
                               "completed": 1, "total": 1,
                               "message": f"Nível {level} concluído."})
            return [result]
        return _json_response({"job": submit(operation, total=1)}, 202)
    except ValueError as exc:
        return _json_response({"error": str(exc)}, 400)


def _manga(payload: dict, output_root: Path) -> Path:
    provider, name = _value(payload, "provider"), _value(payload, "manga")
    if not provider or not name or name not in build_catalog(output_root).get(provider, []):
        raise ValueError("Obra inválida ou fora do catálogo.")
    return resolve_manga(output_root, provider, name)


def _value(payload: dict, key: str) -> str:
    value = payload.get(key)
    return str(value[0] if isinstance(value, list) and value else value or "")


def _json_response(value: dict, status: int = 200) -> RouteResponse:
    body = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return RouteResponse(status, body)
