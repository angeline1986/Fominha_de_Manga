"""Query persisted Level I evidence for an already resolved selection."""
from pathlib import Path

from processamento.unificacao_imagens.auto_merge.nivel1 import (
    read_attempt, read_level1, read_official,
)
from processamento.unificacao_imagens.image_stitcher import list_pages


def query_level1(manga: Path, chapters: list[str]) -> list[dict]:
    rows = []
    root = (manga / "IMG").resolve()
    if not root.is_relative_to(manga.resolve()):
        raise ValueError("Diretório de imagens fora da obra.")
    for name in chapters:
        chapter = (root / name).resolve()
        if chapter.parent != root or not chapter.is_dir():
            raise ValueError("Capítulo fora do diretório de imagens da obra.")
        try:
            pages = len(list_pages(chapter))
        except OSError:
            pages = None
        rows.append({
            "chapter": name, "pages": pages,
            "level1": read_level1(manga, name),
            "attempt": read_attempt(manga, name),
            "official": read_official(manga, name),
            "clean": (manga / "FLUXO_SECUNDARIO" / "04_TEXTO_OFF" / "ORIGINAL"
                      / name / "clean-manifest.json").is_file(),
            "pdf_merge": (manga / "FLUXO_SECUNDARIO" / "03_PDF_MERGE"
                          / name / f"{name}.pdf").is_file(),
        })
    return rows
