"""Resolve an authorized image selected in the Laboratory."""
from pathlib import Path

from central_v2.backend.routes.laboratorio_pages import _chapter, _directory, _images
from central_v2.backend.state.catalog import build_catalog
from central_v2.backend.state.manga_state import IMAGE_EXTENSIONS, resolve_manga


def resolve_source(payload, output_root):
    provider = payload.get("provider")
    manga_name = payload.get("manga")
    chapter = payload.get("chapter")
    filename = payload.get("page")
    kind = payload.get("source")
    if any(not isinstance(value, str) or not value or len(value) > 240
           for value in (provider, manga_name, chapter, filename)):
        raise ValueError("Contexto incompleto.")
    if kind == "file":
        relative = payload.get("path")
        if not isinstance(relative, str) or not relative or len(relative) > 1024:
            raise ValueError("Caminho da imagem inválido.")
        parts = relative.split("/")
        if (any(part in {"", ".", ".."} or part.startswith(".") for part in parts)
                or "\\" in relative or Path(relative).is_absolute()):
            raise ValueError("Caminho da imagem inválido.")
        if manga_name not in build_catalog(output_root).get(provider, []):
            raise ValueError("Obra fora do catálogo.")
        manga = resolve_manga(output_root, provider, manga_name).resolve()
        path = manga.joinpath(*parts).resolve()
        parent_name = parts[-2] if len(parts) > 1 else manga_name
        if (not path.is_relative_to(manga) or not path.is_file()
                or path.suffix.lower() not in IMAGE_EXTENSIONS
                or parent_name != chapter or parts[-1] != filename):
            raise ValueError("Imagem fora do catálogo autorizado.")
        return manga, path, chapter, filename
    if kind not in {"img", "merge"}:
        raise ValueError("Origem inválida.")
    image_root = _directory(output_root, provider, manga_name, kind)
    folder = _chapter(image_root, chapter)
    pages = {page.name: page.resolve() for page in _images(folder)}
    if filename not in pages:
        raise ValueError("Página fora do catálogo autorizado.")
    manga = image_root.parent if kind == "img" else image_root.parents[1]
    return manga.resolve(), pages[filename], chapter, filename
