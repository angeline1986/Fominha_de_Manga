"""Select chapters with current directed Level IV residuals."""
from pathlib import Path

from PIL import Image

from processamento.unificacao_imagens import image_stitcher as v3
from processamento.unificacao_imagens.auto_merge.nivel1 import read_official
from processamento.unificacao_imagens.auto_merge.nivel4 import read_level4


def _regions(chapter: Path, residuals: list[dict]) -> tuple[int, list[str]]:
    cursor, pages, files, regions = 0, [], set(), []
    for path in v3.list_pages(chapter):
        with Image.open(path) as image:
            height = image.height
        pages.append((path.name, cursor, cursor + height)); cursor += height
    for residual in residuals:
        covered = [name for name, start, end in pages
                   if end > residual["global_start"] and start < residual["global_end"]]
        if not covered:
            raise ValueError("Residual do Nível IV sem imagem-fonte correspondente.")
        files.update(covered); regions.append(f"{covered[0]} → {covered[-1]}")
    return len(files), regions


def query_level5(manga: Path, chapters: list[str]) -> list[dict]:
    rows, root = [], (manga / "IMG").resolve()
    if not root.is_relative_to(manga.resolve()):
        raise ValueError("Diretório de imagens fora da obra.")
    for name in chapters:
        chapter = (root / name).resolve()
        if chapter.parent != root or not chapter.is_dir():
            raise ValueError("Capítulo fora do diretório de imagens da obra.")
        stage = manga / "FLUXO_SECUNDARIO" / "01_MERGE_PROCESSAMENTO" / "MERGE_LEVEL5" / name
        if stage.exists() or v3.merge_output_dir(chapter).exists():
            continue
        level4, official = read_level4(manga, name), read_official(manga, name)
        if level4.status != "recorded" or official.status != "absent":
            continue
        residuals = level4.data["residuals"]
        if not residuals:
            continue
        count, regions = _regions(chapter, residuals)
        rows.append({"chapter": name, "pages": len(v3.list_pages(chapter)),
                     "residual_segments": len(residuals), "residual_images": count,
                     "residual_regions": regions, "safe_artifacts": len(level4.data["safe_artifacts"])})
    return rows
