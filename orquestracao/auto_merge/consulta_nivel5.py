"""Select chapters with current directed Level IV residuals."""
from pathlib import Path
import hashlib

from PIL import Image

from processamento.unificacao_imagens import image_stitcher as v3
from processamento.unificacao_imagens.auto_merge.nivel1 import read_official
from processamento.unificacao_imagens.auto_merge.nivel4 import read_level4
from processamento.unificacao_imagens.auto_merge.documentos import Document, read_document


def _read_level5(manga: Path, chapter: str) -> Document:
    directory = manga / "FLUXO_SECUNDARIO" / "01_MERGE_PROCESSAMENTO" / "MERGE_LEVEL5" / chapter
    record = read_document(directory / "merge-level5-manifest.json", manga)
    if record.status != "recorded":
        return record
    parent = read_level4(manga, chapter)
    if parent.status != "recorded":
        return Document("invalid", error="Manifesto do Nível IV não autoriza o histórico do Nível V.")
    data = record.data
    source = manga / "FLUXO_SECUNDARIO" / "01_MERGE_PROCESSAMENTO" / "MERGE_LEVEL4" / chapter / "merge-level4-manifest.json"
    try:
        if data.get("algorithm") != "merge_level5_global_structural_safe_v1" or data.get("schema_version") != 1:
            raise ValueError("Formato do manifesto do Nível V inválido.")
        if data.get("chapter") != chapter or data.get("total_height") != parent.data["total_height"]:
            raise ValueError("Manifesto do Nível V incompatível com o capítulo.")
        if data.get("source_level4_sha256") != hashlib.sha256(source.read_bytes()).hexdigest():
            raise ValueError("Manifesto do Nível V desatualizado em relação ao Nível IV.")
        residuals = data.get("residual_pending_segments")
        artifacts = data.get("safe_artifacts")
        if not isinstance(residuals, list) or not isinstance(artifacts, list):
            raise ValueError("Lista de resultados do Nível V inválida.")
        for item in residuals + artifacts:
            if not isinstance(item, dict) or type(item.get("global_start")) is not int or type(item.get("global_end")) is not int:
                raise ValueError("Intervalo inválido no manifesto do Nível V.")
            if not 0 <= item["global_start"] < item["global_end"] <= data["total_height"]:
                raise ValueError("Coordenadas inválidas no manifesto do Nível V.")
        return Document("recorded", {"residuals": residuals, "safe_artifacts": artifacts})
    except (OSError, ValueError, TypeError) as exc:
        return Document("invalid", error=str(exc))


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


def query_level5(manga: Path, chapters: list[str], *, include_history: bool = False) -> list[dict]:
    rows, root = [], (manga / "IMG").resolve()
    if not root.is_relative_to(manga.resolve()):
        raise ValueError("Diretório de imagens fora da obra.")
    for name in chapters:
        chapter = (root / name).resolve()
        if chapter.parent != root or not chapter.is_dir():
            raise ValueError("Capítulo fora do diretório de imagens da obra.")
        stage = manga / "FLUXO_SECUNDARIO" / "01_MERGE_PROCESSAMENTO" / "MERGE_LEVEL5" / name
        if include_history and stage.exists():
            record = _read_level5(manga, name)
            if record.status == "recorded":
                residuals = record.data["residuals"]
                count, regions = _regions(chapter, residuals) if residuals else (0, [])
                rows.append({"chapter": name, "pages": len(v3.list_pages(chapter)),
                             "residual_segments": len(residuals), "residual_images": count,
                             "residual_regions": regions, "safe_artifacts": len(record.data["safe_artifacts"]),
                             "eligible": False, "status": "Parcial" if residuals else "Resolvido"})
            else:
                rows.append({"chapter": name, "pages": len(v3.list_pages(chapter)),
                             "residual_segments": 0, "residual_images": 0, "residual_regions": [],
                             "safe_artifacts": 0, "eligible": False, "status": "Registro inválido"})
            continue
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
                     "residual_regions": regions, "safe_artifacts": len(level4.data["safe_artifacts"]),
                     "eligible": True, "status": "Disponível"})
    return rows
