"""Serve Laboratory images from the Glass and saved Check stages."""
import json
import mimetypes
from urllib.parse import urlencode

from central_v2.backend.routes.laboratorio_check_pages import (
    check_chapter_names, check_pages, other_pages,
)
from central_v2.backend.routes.laboratorio_glass_pages import (
    check_page_for_glass, glass_chapter, glass_chapter_names,
)
from central_v2.backend.routes.laboratorio_image_files import _images
from central_v2.backend.routes.response import RouteResponse
from central_v2.backend.state.catalog import build_catalog
from central_v2.backend.state.manga_state import resolve_manga
from central_v2.backend.state.sorting import natural_sort_key


def _arg(query, name):
    return (query.get(name) or [""])[0]


def _stage_pages(manga, provider, source, chapter):
    if source == "check":
        return check_pages(manga, provider, chapter)
    folder = glass_chapter(manga, chapter)
    marked = other_pages(manga, provider, chapter)
    return {path.name: path for path in _images(folder)
            if check_page_for_glass(path.name) in marked}


def stage_response(query, output_root, provider, name, image):
    if name not in build_catalog(output_root).get(provider, []):
        raise ValueError("Obra não encontrada no catálogo.")
    manga = resolve_manga(output_root, provider, name)
    source = _arg(query, "source")
    if image:
        pages = _stage_pages(manga, provider, source, _arg(query, "chapter"))
        page = _arg(query, "page")
        selected = pages.get(page)
        if selected is None:
            raise ValueError("Imagem da etapa indisponível.")
        return RouteResponse(200, selected.read_bytes(),
                             mimetypes.guess_type(page)[0] or "image/png")
    names = check_chapter_names(manga) if source == "check" else glass_chapter_names(manga)
    chapters = {}
    for chapter in names:
        try:
            pages = _stage_pages(manga, provider, source, chapter)
        except (OSError, ValueError):
            continue
        chapters[chapter] = [{"name": page,
            "previewUrl": "/api/textoff/laboratorio/pages/image?" + urlencode({
                "provider": provider, "manga": name, "source": source,
                "chapter": chapter, "page": page})}
            for page in sorted(pages, key=natural_sort_key)]
    body = {"provider": provider, "manga": name, "chapters": chapters}
    return RouteResponse(200, json.dumps(body, ensure_ascii=False).encode("utf-8"))
