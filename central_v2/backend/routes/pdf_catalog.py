"""Inventário de candidatos à geração de PDF — somente leitura.

A contagem de arquivos NÃO substitui a validação oficial do MERGE.
"""
import json
from pathlib import Path

from central_v2.backend.routes.response import RouteResponse
from central_v2.backend.state.manga_state import resolve_manga, IMAGE_EXTENSIONS
from central_v2.backend.state.sorting import natural_sort_key


def _images(folder, manga):
    if not folder.is_dir() or not folder.resolve().is_relative_to(manga):
        return []
    return sorted((p for p in folder.iterdir()
                   if p.is_file() and not p.name.startswith('.')
                   and p.suffix.lower() in IMAGE_EXTENSIONS
                   and not p.stem.lower().endswith('_old')
                   and p.resolve().is_relative_to(folder.resolve())),
                  key=lambda p: natural_sort_key(p.name))


def response(query, output_root: Path):
    provider = (query.get('provider') or [''])[0]
    manga_name = (query.get('manga') or [''])[0]
    source = (query.get('source') or [''])[0]
    if source not in {'original', 'merged'}:
        return _json({'error': 'Origem invalida.'}, 400)
    try:
        manga = resolve_manga(output_root, provider, manga_name).resolve()
        img_root = manga / 'IMG'
        merge_root = manga / 'FLUXO_SECUNDARIO' / '02_MERGE'
        pdf_root = (manga / 'PDF') if source == 'original' else (manga / 'FLUXO_SECUNDARIO' / '03_PDF_MERGE')
        chapters = []
        if img_root.is_dir():
            for folder in sorted(img_root.iterdir(), key=lambda p: natural_sort_key(p.name)):
                if not folder.is_dir() or not folder.resolve().is_relative_to(img_root.resolve()):
                    continue
                original_count = len(_images(folder, manga))
                if original_count == 0:
                    continue
                merge_count = len(_images(merge_root / folder.name, manga))
                image_count = original_count if source == 'original' else merge_count
                pdf = pdf_root / folder.name / (folder.name + '.pdf')
                has_pdf = pdf.is_file() and pdf.resolve().is_relative_to(manga)
                chapters.append({'chapter': folder.name, 'image_count': image_count,
                                 'merge_image_count': merge_count, 'has_pdf': has_pdf,
                                 'pdf_bytes': pdf.stat().st_size if has_pdf else None,
                                 'candidate': image_count > 0})
        return _json({'provider': provider, 'manga': manga_name, 'source': source,
                      'chapters': chapters, 'read_only': True,
                      'warning': 'A contagem de imagens nao comprova elegibilidade ou MERGE oficial.'})
    except (ValueError, OSError) as exc:
        return _json({'error': str(exc)}, 400)


def _json(data, status=200):
    return RouteResponse(status, json.dumps(data, ensure_ascii=False).encode('utf-8'))
