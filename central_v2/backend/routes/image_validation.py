"""Contratos HTTP da validação de imagens da Central V2."""

from io import BytesIO
import json
import mimetypes
from pathlib import Path

from PIL import Image

from central_v2.backend.jobs.manager import submit
from central_v2.backend.routes.response import RouteResponse
from central_v2.backend.state.image_validation import (
    analyze, catalog, chapter_directories, read_chapter, record_application,
    validate_chapters,
)
from central_v2.backend.state.manga_state import resolve_manga
from orquestracao.central_session import legacy_server_active
from processamento.validacao_imagens.corretor_dimensoes import corrigir_imagem


def _json(payload: dict, status: int = 200) -> RouteResponse:
    return RouteResponse(status, json.dumps(payload, ensure_ascii=False,
                                            separators=(",", ":")).encode("utf-8"))


def _context(values: dict, output_root: Path) -> tuple[Path, str, str]:
    provider = values.get("provider")
    name = values.get("manga")
    if not isinstance(provider, str) or not isinstance(name, str) or not provider or not name:
        raise ValueError("Selecione um provider e uma obra.")
    return resolve_manga(output_root, provider, name), provider, name


def _one(query: dict, key: str) -> str:
    return (query.get(key) or [""])[0]


def dispatch_get(path: str, query: dict, output_root: Path) -> RouteResponse | None:
    if path == "/api/images/validation":
        return state_response(query, output_root)
    if path == "/api/images/validation/image":
        return image_response(query, output_root)
    return None


def state_response(query: dict, output_root: Path) -> RouteResponse:
    try:
        manga, provider, name = _context({"provider": _one(query, "provider"),
                                          "manga": _one(query, "manga")}, output_root)
        return _json(catalog(manga, provider, name))
    except ValueError as exc:
        return _json({"error": str(exc)}, 400)
    except (OSError, KeyError, TypeError, json.JSONDecodeError):
        return _json({"error": "Não foi possível consultar a validação da obra."}, 500)


def image_response(query: dict, output_root: Path) -> RouteResponse:
    try:
        manga, _, _ = _context({"provider": _one(query, "provider"),
                                "manga": _one(query, "manga")}, output_root)
        chapter, filename = _one(query, "chapter"), _one(query, "file")
        proposed = _one(query, "variant") == "proposed"
        if not chapter or not filename or Path(chapter).name != chapter or Path(filename).name != filename:
            raise ValueError("Imagem inválida.")
        record = read_chapter(manga, chapter)
        analysis = record.get("analysis", {}) if record else {}
        image = next((item for item in analysis.get("images", []) if item.get("file") == filename
                      and item.get("classification") == "EXCECAO_DIMENSAO"), None)
        if not image:
            raise ValueError("Execute a validação antes de visualizar esta página.")
        source = chapter_directories(manga)[chapter] / filename
        if not source.is_file() or source.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
            raise ValueError("Imagem não encontrada.")
        if not proposed:
            return RouteResponse(200, source.read_bytes(),
                                 mimetypes.guess_type(filename)[0] or "application/octet-stream")
        width = int(analysis["dominant_width"])
        with Image.open(source) as original:
            if original.size != (image["width"], image["height"]):
                raise ValueError("A imagem mudou desde a análise. Execute novamente.")
            height = max(1, round(original.height * width / original.width))
            preview = original.resize((width, height), Image.Resampling.LANCZOS)
            output = BytesIO()
            fmt = original.format if original.format in {"PNG", "JPEG", "WEBP"} else "PNG"
            preview.save(output, format=fmt)
        mime = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}[fmt]
        return RouteResponse(200, output.getvalue(), mime)
    except (ValueError, KeyError) as exc:
        return _json({"error": str(exc)}, 400)
    except (OSError, TypeError, json.JSONDecodeError):
        return _json({"error": "Não foi possível abrir a imagem."}, 500)


def analyze_response(payload: object, output_root: Path) -> RouteResponse:
    try:
        if not isinstance(payload, dict):
            raise ValueError("Solicitação inválida.")
        manga, _, _ = _context(payload, output_root)
        chapters = validate_chapters(manga, payload.get("chapters"))
        tolerance = float(payload.get("tolerance", 3))
        if not 0 <= tolerance <= 100:
            raise ValueError("A tolerância deve estar entre 0% e 100%.")
        def operation(progress, _job_id):
            try:
                return analyze(manga, chapters, tolerance, progress)
            except OSError as exc:
                raise RuntimeError("Falha ao ler as imagens ou salvar a análise.") from exc
        return _json({"job": submit(operation, total=len(chapters))}, 202)
    except (TypeError, ValueError) as exc:
        return _json({"error": str(exc)}, 400)
    except OSError:
        return _json({"error": "Não foi possível iniciar a validação."}, 500)


def apply_response(payload: object, output_root: Path) -> RouteResponse:
    try:
        if not isinstance(payload, dict):
            raise ValueError("Solicitação inválida.")
        manga, _, _ = _context(payload, output_root)
        chapter, filename = payload.get("chapter"), payload.get("file")
        if not isinstance(chapter, str) or not isinstance(filename, str):
            raise ValueError("Capítulo ou página inválida.")
        validate_chapters(manga, [chapter])
        record = read_chapter(manga, chapter)
        image = next((item for item in record["analysis"]["images"]
                      if item["file"] == filename and item["classification"] == "EXCECAO_DIMENSAO"), None) if record else None
        if not image:
            raise ValueError("A análise desta página expirou. Execute a validação novamente.")
        if legacy_server_active():
            raise ValueError("Feche a Central V1 antes de aplicar a correção na V2.")

        def operation(progress, _job_id):
            if legacy_server_active():
                raise ValueError("Central V1 ativa; correção cancelada por segurança.")
            current = read_chapter(manga, chapter)
            if current != record:
                raise ValueError("A análise mudou. Execute a validação novamente.")
            directory = chapter_directories(manga)[chapter]
            source = directory / filename
            try:
                result = corrigir_imagem(source, (image["width"], image["height"]),
                                         int(record["analysis"]["dominant_width"]))
                record_application(manga, chapter, filename,
                                   float(record["analysis"]["tolerance_percent"]))
            except OSError as exc:
                raise RuntimeError(f"Falha ao corrigir {filename} no capítulo {chapter}.") from exc
            progress(chapter, {"completed": 1, "total": 1, "percent": 100,
                               "message": f"Cap. {chapter}: {filename} corrigida."})
            return [{"chapter": chapter, "status": "applied", **result}]

        return _json({"job": submit(operation, total=1)}, 202)
    except (TypeError, ValueError, KeyError) as exc:
        return _json({"error": str(exc)}, 400)
    except (OSError, json.JSONDecodeError):
        return _json({"error": "Não foi possível iniciar a correção."}, 500)
