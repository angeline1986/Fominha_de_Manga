"""Select chapters with validated Level I residuals eligible for Level II."""
from pathlib import Path
from PIL import Image

from processamento.unificacao_imagens.auto_merge.nivel1 import (
    read_level1,
    read_official,
)
from processamento.unificacao_imagens.auto_merge.nivel2 import read_level2
from processamento.unificacao_imagens.image_stitcher import list_pages
from processamento.unificacao_imagens.image_stitcher import page_range_output_name


def _eligible(document, official, level2_directory: Path) -> bool:
    if document.status != "recorded" or official.status != "absent":
        return False
    data = document.data or {}
    if data.get("kind") != "partial" or not data.get("residuals"):
        return False
    return not level2_directory.exists() and bool(data.get("artifacts")) and all(
        item.get("exists") for item in data["artifacts"]
    )


def _regions(chapter: Path, residuals: list[dict]) -> list[str]:
    pages, cursor = [], 0
    for path in list_pages(chapter):
        try:
            with Image.open(path) as image:
                height = image.height
        except OSError:
            return ["Origem não identificada"] * len(residuals)
        pages.append((path.name, cursor, cursor + height))
        cursor += height
    regions = []
    for residual in residuals:
        sources = [name for name, start, end in pages
                   if end > residual["global_start"] and start < residual["global_end"]]
        if not sources:
            regions.append("Origem não identificada")
        else:
            regions.append(page_range_output_name(sources[0], sources[-1]))
    return regions


def query_level2(manga: Path, chapters: list[str], *, include_history: bool = False) -> list[dict]:
    rows = []
    root = (manga / "IMG").resolve()
    if not root.is_relative_to(manga.resolve()):
        raise ValueError("Diretório de imagens fora da obra.")
    for name in chapters:
        chapter = (root / name).resolve()
        if chapter.parent != root or not chapter.is_dir():
            raise ValueError("Capítulo fora do diretório de imagens da obra.")
        level1 = read_level1(manga, name)
        official = read_official(manga, name)
        level2_directory = manga / "FLUXO_SECUNDARIO" / "01_MERGE_PROCESSAMENTO" / "MERGE_LEVEL2" / name
        if include_history and level2_directory.exists():
            record = read_level2(manga, name)
            if record.status == "recorded":
                residuals = record.data["residuals"]
                rows.append({
                    "chapter": name, "pages": len(list_pages(chapter)),
                    "residual_segments": len(residuals),
                    "residual_height": sum(item["global_end"] - item["global_start"] for item in residuals),
                    "residuals": residuals, "residual_regions": _regions(chapter, residuals),
                    "level1_artifacts": len(level1.data.get("artifacts", [])) if level1.data else 0,
                    "level2_artifacts": len(record.data["artifacts"]),
                    "eligible": False, "status": "Parcial" if residuals else "Resolvido",
                })
            else:
                rows.append({"chapter": name, "pages": len(list_pages(chapter)),
                             "residual_segments": 0, "residual_regions": [], "eligible": False,
                             "status": "Registro inválido", "error": record.error or "Manifesto do Nível II inválido."})
            continue
        if not _eligible(level1, official, level2_directory):
            continue
        data = level1.data
        residuals = data["residuals"]
        rows.append({
            "chapter": name,
            "pages": len(list_pages(chapter)),
            "residual_segments": len(residuals),
            "residual_height": sum(
                item["global_end"] - item["global_start"] for item in residuals
            ),
            "residuals": residuals,
            "residual_regions": _regions(chapter, residuals),
            "level1_artifacts": len(data["artifacts"]),
            "eligible": True, "status": "Disponível",
        })
    return rows
