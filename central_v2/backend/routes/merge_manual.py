import json
import hashlib
from pathlib import Path
from urllib.parse import parse_qs

from config.data_paths import OUTPUT_ROOT
from central_v2.backend.routes.response import RouteResponse
from processamento.merge_manual.api import (
    apply_merge_manual_proposal_job,
    generate_merge_manual_proposal_job,
    get_merge_manual_state,
)
from processamento.merge_manual.proposal import MANIFEST_NAME, proposal_dir
from processamento.unificacao_imagens.auto_merge.documentos import read_document
from central_v2.backend.state.manga_state import resolve_manga
from central_v2.backend.state.work_layout import images_root, processing_stage_root


def _review_row(manga: Path, chapter: str) -> dict:
    directory = processing_stage_root(manga, "MERGE_LEVEL5") / chapter
    path = directory / "merge-level5-manifest.json"
    record = read_document(path, manga)
    if record.status == "absent":
        return {"needs_review": False, "merge_state": "novo"}
    if record.status != "recorded":
        detail = {"available": True, "valid": False, "error": record.error}
    else:
        data = record.data or {}
        level4_path = processing_stage_root(manga, "MERGE_LEVEL4") / chapter / "merge-level4-manifest.json"
        pending = data.get("residual_pending_segments")
        total = data.get("total_height")
        valid = (
            data.get("algorithm") == "merge_level5_global_structural_safe_v1"
            and data.get("schema_version") == 1
            and data.get("chapter") == chapter
            and type(total) is int and total > 0
            and isinstance(pending, list)
            and level4_path.is_file()
            and data.get("source_level4_sha256") == hashlib.sha256(level4_path.read_bytes()).hexdigest()
            and all(type(item.get("global_start")) is int and type(item.get("global_end")) is int
                    and 0 <= item["global_start"] < item["global_end"] <= total
                    for item in pending if isinstance(item, dict))
            and all(isinstance(item, dict) for item in pending)
        )
        detail = {
            "available": True,
            "valid": valid,
            "error": None if valid else "Manifesto do Nível V incompatível ou inválido.",
            "review_pending_segments": pending if valid else [],
        }
    return {"needs_review": True, "merge_state": "pendente_review", "merge_level5_detail": detail}


def _applied_manual_range(manga: Path, chapter: str) -> dict | None:
    """Lê a faixa manual que está registrada na composição oficial atual."""
    official_path = manga / "FLUXO_SECUNDARIO" / "02_MERGE" / chapter / "merge-manifest.json"
    try:
        official = json.loads(official_path.read_text(encoding="utf-8"))
        if not isinstance(official, dict):
            return None
        composition = official.get("composition") or {}
        if not isinstance(composition, dict):
            return None
        proposal_id = str(composition.get("manual_proposal_id") or "")
        bounds = composition.get("manual_range")
        if not proposal_id or not isinstance(bounds, list) or len(bounds) != 2:
            return None
        start, end = int(bounds[0]), int(bounds[1])
        proposal_path = (
            manga / "FLUXO_SECUNDARIO" / "01_MERGE_PROCESSAMENTO"
            / "MERGE_MANUAL_PROPOSALS" / chapter / proposal_id / MANIFEST_NAME
        )
        proposal = json.loads(proposal_path.read_text(encoding="utf-8"))
        if (
            not isinstance(proposal, dict)
            or proposal.get("proposal_id") != proposal_id
            or proposal.get("chapter") != chapter
            or proposal.get("status") != "EFETIVADO"
            or start < 0
            or end <= start
        ):
            return None
        return {"global_start": start, "global_end": end, "proposal_id": proposal_id}
    except (AttributeError, OSError, ValueError, TypeError, json.JSONDecodeError):
        return None


def _chapter_review_row(manga: Path, chapter: str) -> dict:
    row = _review_row(manga, chapter)
    applied = _applied_manual_range(manga, chapter)
    if applied:
        row["merge_manual_applied_range"] = applied
    return row


def merge_manual_response(query: dict, output_root: Path = OUTPUT_ROOT) -> RouteResponse:
    provider = (query.get("provider") or [""])[0]
    name = (query.get("manga") or [""])[0]
    if not provider or not name:
        return RouteResponse(400, b'{"error":"provider e manga sao obrigatorios"}')
    try:
        manga = resolve_manga(output_root, provider, name)
        root = images_root(manga)
        chapters = [item for item in root.iterdir() if item.is_dir()] if root.is_dir() else []
        payload = get_merge_manual_state(
            manga, chapters,
            review_state_loader=lambda chapter: _chapter_review_row(manga, chapter.name),
        )
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
        return RouteResponse(200, body)
    except (OSError, ValueError) as exc:
        body = json.dumps({"error": str(exc)}, ensure_ascii=False).encode()
        return RouteResponse(400, body)


def merge_manual_image_response(query: dict, output_root: Path = OUTPUT_ROOT) -> RouteResponse:
    provider = (query.get("provider") or [""])[0]
    manga_name = (query.get("manga") or [""])[0]
    chapter = (query.get("chapter") or [""])[0]
    filename = (query.get("file") or [""])[0]
    if not all((provider, manga_name, chapter, filename)) or Path(filename).name != filename:
        return RouteResponse(400, b'{"error":"parametros invalidos"}')
    try:
        manga = resolve_manga(output_root, provider, manga_name)
        root = images_root(manga).resolve()
        directory = (root / chapter).resolve()
        target = (directory / filename).resolve()
        if directory.parent != root or not target.is_relative_to(directory) or not target.is_file():
            return RouteResponse(404, b'{"error":"imagem nao encontrada"}')
        if target.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
            return RouteResponse(404, b'{"error":"imagem nao encontrada"}')
        import mimetypes
        return RouteResponse(200, target.read_bytes(), mimetypes.guess_type(target.name)[0] or "application/octet-stream")
    except (OSError, ValueError):
        return RouteResponse(404, b'{"error":"imagem nao encontrada"}')


def merge_manual_proposal_response(payload: object, output_root: Path = OUTPUT_ROOT) -> RouteResponse:
    if not isinstance(payload, dict):
        return RouteResponse(400, b'{"error":"payload invalido"}')
    provider, name = str(payload.get("provider") or ""), str(payload.get("manga") or "")
    try:
        manga = resolve_manga(output_root, provider, name)
        root = images_root(manga)
        chapters = [item for item in root.iterdir() if item.is_dir()] if root.is_dir() else []
        result = generate_merge_manual_proposal_job(
            manga, chapters,
            review_state_loader=lambda chapter: _chapter_review_row(manga, chapter.name),
            payload=payload,
        )
        body = json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode()
        return RouteResponse(201, body)
    except (OSError, ValueError) as exc:
        body = json.dumps({"error": str(exc)}, ensure_ascii=False).encode()
        return RouteResponse(400, body)


def merge_manual_proposal_image_response(query: dict, output_root: Path = OUTPUT_ROOT) -> RouteResponse:
    provider = (query.get("provider") or [""])[0]
    name = (query.get("manga") or [""])[0]
    chapter = (query.get("chapter") or [""])[0]
    proposal_id = (query.get("proposal_id") or [""])[0]
    filename = (query.get("file") or [""])[0]
    if not all((provider, name, chapter, proposal_id, filename)) or Path(chapter).name != chapter or Path(filename).name != filename:
        return RouteResponse(400, b'{"error":"parametros invalidos"}')
    try:
        manga = resolve_manga(output_root, provider, name)
        directory = proposal_dir(manga, chapter, proposal_id).resolve()
        manifest_path = directory / MANIFEST_NAME
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(manifest, dict) or not isinstance(manifest.get("outputs"), list):
            return RouteResponse(404, b'{"error":"imagem da proposta nao encontrada"}')
        allowed = {str(item.get("file")) for item in manifest["outputs"] if isinstance(item, dict)}
        target = (directory / filename).resolve()
        if manifest.get("proposal_id") != proposal_id or manifest.get("chapter") != chapter:
            raise ValueError("Proposta incompatível.")
        if filename not in allowed or not target.is_relative_to(directory) or not target.is_file():
            return RouteResponse(404, b'{"error":"imagem da proposta nao encontrada"}')
        if target.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
            return RouteResponse(404, b'{"error":"imagem da proposta nao encontrada"}')
        import mimetypes
        return RouteResponse(200, target.read_bytes(), mimetypes.guess_type(target.name)[0] or "application/octet-stream")
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return RouteResponse(404, b'{"error":"imagem da proposta nao encontrada"}')


def merge_manual_apply_response(payload: object, output_root: Path = OUTPUT_ROOT) -> RouteResponse:
    if not isinstance(payload, dict):
        return RouteResponse(400, b'{"error":"payload invalido"}')
    provider, name = str(payload.get("provider") or ""), str(payload.get("manga") or "")
    try:
        manga = resolve_manga(output_root, provider, name)
        root = images_root(manga)
        chapters = [item for item in root.iterdir() if item.is_dir()] if root.is_dir() else []
        result = apply_merge_manual_proposal_job(
            manga, chapters,
            review_state_loader=lambda chapter: _chapter_review_row(manga, chapter.name),
            payload=payload,
        )
        body = json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode()
        return RouteResponse(200, body)
    except (OSError, ValueError) as exc:
        body = json.dumps({"error": str(exc)}, ensure_ascii=False).encode()
        return RouteResponse(400, body)
