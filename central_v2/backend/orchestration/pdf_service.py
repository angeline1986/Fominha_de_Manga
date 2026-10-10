"""PDF optimized export for Central V2; read-only sources, create-only outputs."""
from __future__ import annotations

import io
import os
import tempfile
from pathlib import Path

import fitz
from PIL import Image, ImageOps

from central_v2.backend.state.manga_state import IMAGE_EXTENSIONS
from central_v2.backend.state.sorting import natural_sort_key
from processamento.unificacao_imagens.image_stitcher import is_chapter_merged, merge_artifact_files


def source_images(manga: Path, chapter: str, source: str) -> list[Path]:
    image_root = manga / 'IMG' / chapter
    if not image_root.is_dir():
        raise ValueError(f'Cap. {chapter}: imagens originais indisponíveis.')
    if source == 'merged':
        if not is_chapter_merged(image_root):
            raise ValueError(f'Cap. {chapter}: MERGE oficial inválido ou ausente.')
        folder = manga / 'FLUXO_SECUNDARIO' / '02_MERGE' / chapter
        paths = merge_artifact_files(folder)
    else:
        folder = image_root
        paths = sorted((f for f in folder.iterdir() if f.is_file() and not f.name.startswith('.')
                        and f.suffix.lower() in IMAGE_EXTENSIONS and not f.stem.lower().endswith('_old')),
                       key=lambda f: natural_sort_key(f.name))
    folder = folder.resolve()
    if not paths or any(not p.is_file() or not p.resolve().is_relative_to(folder) for p in paths):
        raise ValueError(f'Cap. {chapter}: conjunto de imagens ausente ou inseguro.')
    return paths


def generate(manga: Path, chapter: str, source: str, quality: int) -> dict:
    dest_root = manga / ('PDF' if source == 'original' else 'FLUXO_SECUNDARIO/03_PDF_MERGE')
    dest = dest_root / chapter / (chapter + '.pdf')
    if dest.exists():
        return {'chapter': chapter, 'status': 'skipped', 'message': 'PDF existente preservado.'}
    paths = source_images(manga, chapter, source)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp_name = None
    doc = fitz.open()
    try:
        for path in paths:
            with Image.open(path) as source_image:
                image = ImageOps.exif_transpose(source_image)
                if image.mode == 'RGBA' or 'transparency' in image.info:
                    rgba = image.convert('RGBA')
                    rgb = Image.new('RGB', rgba.size, 'white')
                    rgb.paste(rgba, mask=rgba.getchannel('A'))
                    rgba.close()
                else:
                    rgb = image.convert('RGB')
                try:
                    buffer = io.BytesIO()
                    rgb.save(buffer, 'JPEG', quality=quality, subsampling=0, optimize=True)
                    w, h = rgb.size
                    page = doc.new_page(width=w * .75, height=h * .75)
                    page.insert_image(page.rect, stream=buffer.getvalue(), keep_proportion=True)
                finally:
                    rgb.close()
        with tempfile.NamedTemporaryFile(dir=dest.parent, prefix='.pdf-v2-', suffix='.pdf', delete=False) as fd:
            tmp_name = fd.name
        doc.save(tmp_name, garbage=4, deflate=True)
    except Exception:
        if tmp_name:
            Path(tmp_name).unlink(missing_ok=True)
        raise
    finally:
        doc.close()
    try:
        with fitz.open(tmp_name) as verified:
            if verified.is_repaired or not verified.is_pdf or len(verified) != len(paths):
                raise ValueError('PDF gerado não passou na validação estrutural.')
            for p in verified:
                if len(p.get_images(full=True)) != 1:
                    raise ValueError('Uma página do PDF não possui exatamente uma imagem.')
        # Atomic exclusive publication. Never replace an existing PDF.
        os.link(tmp_name, dest)
        return {'chapter': chapter, 'status': 'generated', 'pages': len(paths),
                'bytes': dest.stat().st_size, 'path': str(dest)}
    finally:
        if tmp_name:
            Path(tmp_name).unlink(missing_ok=True)
