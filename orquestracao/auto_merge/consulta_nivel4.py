"""Select chapters with validated Level III residuals for Level IV."""
from pathlib import Path

from PIL import Image

from processamento.unificacao_imagens import image_stitcher as v3
from processamento.unificacao_imagens.auto_merge.nivel1 import read_official
from processamento.unificacao_imagens.auto_merge.nivel3 import read_level3


def _pages(chapter: Path, residuals: list[dict]) -> tuple[int, list[str]]:
    cursor, ranges, files = 0, [], set()
    pages = []
    for path in v3.list_pages(chapter):
        with Image.open(path) as image:
            height = image.height
        pages.append((path.name, cursor, cursor + height))
        cursor += height
    for segment in residuals:
        covered = [name for name, start, end in pages
                   if end > segment["global_start"] and start < segment["global_end"]]
        if not covered:
            raise ValueError("Residual do Nível III sem imagem-fonte correspondente.")
        files.update(covered)
        ranges.append(f"{covered[0]} → {covered[-1]}")
    return len(files), ranges


def query_level4(manga: Path, chapters: list[str]) -> list[dict]:
    rows = []
    root = (manga / "IMG").resolve()
    if not root.is_relative_to(manga.resolve()):
        raise ValueError("Diretório de imagens fora da obra.")
    for name in chapters:
        chapter = (root / name).resolve()
        if chapter.parent != root or not chapter.is_dir():
            raise ValueError("Capítulo fora do diretório de imagens da obra.")
        stage = manga / "FLUXO_SECUNDARIO" / "01_MERGE_PROCESSAMENTO" / "MERGE_LEVEL4" / name
        if stage.exists() or v3.merge_output_dir(chapter).exists():
            continue
        level3, official = read_level3(manga, name), read_official(manga, name)
        if level3.status != "recorded" or official.status != "absent":
            continue
        residuals = level3.data["residuals"]
        if not residuals:
            continue
        count, regions = _pages(chapter, residuals)
        rows.append({"chapter": name, "pages": len(v3.list_pages(chapter)),
                     "residual_segments": len(residuals), "residual_images": count,
                     "residual_regions": regions, "safe_artifacts": len(level3.data["safe_artifacts"])})
    return rows
