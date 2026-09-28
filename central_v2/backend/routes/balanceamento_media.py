"""Manifest-scoped image delivery for Balanceamento previews."""
import json
import mimetypes
from pathlib import Path

from central_v2.backend.routes.response import RouteResponse
from central_v2.backend.state.manga_state import resolve_manga

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


def balanceamento_image_response(query: dict, output_root: Path) -> RouteResponse:
    provider, manga_name = _value(query, "provider"), _value(query, "manga")
    chapter, filename, kind = _value(query, "chapter"), _value(query, "file"), _value(query, "kind")
    proposal_id = _value(query, "proposal_id")
    if (not all((provider, manga_name, chapter, filename, kind))
            or chapter in {".", ".."} or Path(chapter).name != chapter
            or "/" in chapter or "\\" in chapter):
        return _not_found()
    if Path(filename).name != filename or Path(filename).suffix.lower() not in IMAGE_EXTENSIONS:
        return _not_found()
    try:
        manga = resolve_manga(output_root, provider, manga_name).resolve()
        target = _declared_target(manga, chapter, filename, kind, proposal_id)
        if target is None or not target.is_file():
            return _not_found()
        return RouteResponse(200, target.read_bytes(), mimetypes.guess_type(target.name)[0] or "application/octet-stream")
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return _not_found()


def _declared_target(manga: Path, chapter: str, filename: str, kind: str, proposal_id: str) -> Path | None:
    if kind == "merge":
        folder = manga / "FLUXO_SECUNDARIO/02_MERGE" / chapter
        manifest = _read(folder / "merge-manifest.json")
        names = [row.get("file") for row in (manifest or {}).get("outputs", []) if isinstance(row, dict)]
        if filename not in names:
            return None
        base = folder.resolve()
    elif kind in {"editor", "proposal"}:
        secondary = (manga / "FLUXO_SECUNDARIO").resolve()
        status = _read(secondary / "01_MERGE_PROCESSAMENTO/BALANCE_STATUS" / chapter / "balance-status.json")
        if not status or (proposal_id and status.get("proposal_id") != proposal_id):
            return None
        key = "editor_manifest" if kind == "editor" else "proposal_manifest"
        relative = status.get(key)
        manifest_path = (secondary / str(relative or "")).resolve()
        if not relative or not manifest_path.is_relative_to(secondary):
            return None
        manifest = _read(manifest_path)
        if not manifest:
            return None
        field = "source_preview" if kind == "editor" else "artifacts"
        names = [manifest.get(field)] if kind == "editor" else [row.get("file") for row in manifest.get(field, []) if isinstance(row, dict)]
        if filename not in names:
            return None
        base = manifest_path.parent.resolve()
    else:
        return None
    target = (base / filename).resolve()
    return target if target.is_relative_to(base) else None


def _read(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _value(query: dict, key: str) -> str:
    return str((query.get(key) or [""])[0])


def _not_found() -> RouteResponse:
    return RouteResponse(404, b'{"error":"Imagem de Balanceamento nao encontrada"}')
