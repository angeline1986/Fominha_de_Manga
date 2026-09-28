"""Select chapters with validated Level II residuals eligible for Level III."""
from pathlib import Path
from PIL import Image

from processamento.unificacao_imagens import image_stitcher as v3
from processamento.unificacao_imagens.auto_merge.nivel1 import read_official
from processamento.unificacao_imagens.auto_merge.nivel2 import read_level2


def _page_ranges(chapter: Path, residuals: list[dict]) -> tuple[list[str], list[str]]:
    cursor, pages = 0, []
    for path in v3.list_pages(chapter):
        try:
            with Image.open(path) as image:
                height = image.height
        except OSError:
            raise ValueError("Não foi possível identificar as imagens do capítulo.")
        pages.append((path.name, cursor, cursor + height))
        cursor += height
    regions, files = [], set()
    for residual in residuals:
        covered = [name for name, start, end in pages
                   if end > residual["global_start"] and start < residual["global_end"]]
        if not covered:
            raise ValueError("Residual do Nível II sem imagem-fonte correspondente.")
        files.update(covered)
        regions.append(f"{covered[0]} → {covered[-1]}")
    return regions, sorted(files, key=lambda name: v3.natural_key(Path(name)))


def query_level3(manga: Path, chapters: list[str]) -> list[dict]:
    rows = []
    root = (manga / "IMG").resolve()
    if not root.is_relative_to(manga.resolve()):
        raise ValueError("Diretório de imagens fora da obra.")
    for name in chapters:
        chapter = (root / name).resolve()
        if chapter.parent != root or not chapter.is_dir():
            raise ValueError("Capítulo fora do diretório de imagens da obra.")
        stage = manga / "FLUXO_SECUNDARIO" / "01_MERGE_PROCESSAMENTO" / "MERGE_LEVEL3" / name
        if stage.exists() or v3.merge_output_dir(chapter).exists():
            continue
        level2 = read_level2(manga, name)
        official = read_official(manga, name)
        if level2.status != "recorded" or official.status != "absent":
            continue
        residuals = level2.data["residuals"]
        if not residuals:
            continue
        regions, files = _page_ranges(chapter, residuals)
        rows.append({
            "chapter": name,
            "pages": len(v3.list_pages(chapter)),
            "residual_segments": len(residuals),
            "residual_images": len(files),
            "residual_regions": regions,
            "level2_artifacts": len(level2.data["artifacts"]),
        })
    return rows
