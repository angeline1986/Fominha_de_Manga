"""Consulta isolada, somente leitura, de paginas originais para o Laboratorio."""
import json
import mimetypes
from pathlib import Path
from urllib.parse import urlencode

from central_v2.backend.routes.response import RouteResponse
from central_v2.backend.state.catalog import build_catalog
from central_v2.backend.state.manga_state import resolve_manga, IMAGE_EXTENSIONS
from central_v2.backend.state.sorting import natural_sort_key

ROUTE = "/api/textoff/laboratorio/pages"
IMAGE_ROUTE = ROUTE + "/image"


def _json(data, status=200):
    return RouteResponse(status, json.dumps(data, ensure_ascii=False).encode("utf-8"))


def _arg(query, name):
    return (query.get(name) or [""])[0]


def _directory(output_root, provider, manga_name, source="img"):
    if manga_name not in build_catalog(output_root).get(provider, []):
        raise ValueError("Obra não encontrada no catálogo.")
    manga = resolve_manga(output_root, provider, manga_name)
    if source not in {"img", "merge"}:
        raise ValueError("Origem inválida.")
    relative = "IMG" if source == "img" else "FLUXO_SECUNDARIO/02_MERGE"
    image_root = (manga / relative).resolve()
    if not image_root.is_relative_to(manga.resolve()):
        raise ValueError("Diretório fora da obra.")
    return image_root


def _chapter(image_root, name):
    if not name or Path(name).name != name or name in {".", ".."}:
        raise ValueError("Capítulo inválido.")
    folder = (image_root / name).resolve()
    if not folder.is_relative_to(image_root) or not folder.is_dir():
        raise ValueError("Capítulo indisponível.")
    return folder


def _images(folder):
    return sorted((p for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
        and not p.stem.lower().endswith("_old")
        and p.resolve().is_relative_to(folder.resolve())),
        key=lambda p: natural_sort_key(p.name))


def response(query, output_root, *, image=False):
    try:
        provider, name = _arg(query, "provider"), _arg(query, "manga")
        if _arg(query, "browse") == "1":
            return _browse(output_root, provider, name, _arg(query, "path"))
        image_root = _directory(output_root, provider, name, _arg(query, "source") or "img")
        if not image_root.is_dir():
            return _json({"provider": provider, "manga": name, "chapters": {}}) if not image else _json({"error": "Imagem indisponível."}, 404)
        if image:
            chapter, page = _arg(query, "chapter"), _arg(query, "page")
            folder = _chapter(image_root, chapter)
            if not page or Path(page).name != page or page in {".", ".."}:
                raise ValueError("Página inválida.")
            target = (folder / page).resolve()
            if target not in [p.resolve() for p in _images(folder)]:
                raise ValueError("Imagem indisponível.")
            return RouteResponse(200, target.read_bytes(),
                mimetypes.guess_type(target.name)[0] or "image/png")

        chapters = {}
        for folder in sorted(image_root.iterdir(), key=lambda p: natural_sort_key(p.name)):
            if not folder.is_dir() or not folder.resolve().is_relative_to(image_root):
                continue
            files = _images(folder)
            if not files:
                continue
            chapters[folder.name] = [{
                "name": page.name,
                "previewUrl": IMAGE_ROUTE + "?" + urlencode({
                    "provider": provider, "manga": name,
                    "chapter": folder.name, "page": page.name,
                    "source": _arg(query, "source") or "img",
                }),
            } for page in files]
        return _json({"provider": provider, "manga": name, "chapters": chapters})
    except (ValueError, OSError, TypeError) as exc:
        return _json({"error": str(exc)}, 404)


def _browse(output_root, provider, name, relative_path):
    """Listagem restrita à pasta da obra, sem acesso a arquivos externos."""
    if name not in build_catalog(output_root).get(provider, []):
        raise ValueError("Obra fora do catálogo.")
    manga = resolve_manga(output_root, provider, name).resolve()
    fragments = [part for part in relative_path.split("/") if part]
    if any(part in {".", ".."} for part in fragments) or "\\" in relative_path:
        raise ValueError("Caminho inválido.")
    folder = manga.joinpath(*fragments).resolve()
    if not folder.is_relative_to(manga) or not folder.is_dir():
        raise ValueError("Diretório inválido.")
    entries = []
    for child in sorted(folder.iterdir(), key=lambda p: natural_sort_key(p.name)):
        if child.name.startswith(".") or not child.resolve().is_relative_to(manga):
            continue
        if child.is_dir():
            kind = "directory"
        elif child.is_file() and child.suffix.lower() in IMAGE_EXTENSIONS:
            kind = "file"
        else:
            continue
        entries.append({"name": child.name, "type": kind,
                        "path": "/".join([*fragments, child.name])})
    return _json({"directory": str(folder), "path": "/".join(fragments), "entries": entries})
