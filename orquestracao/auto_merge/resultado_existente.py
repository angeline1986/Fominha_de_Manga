"""Build a non-mutating summary from an existing validated Level I stage."""
from pathlib import Path
from PIL import Image

from processamento.unificacao_imagens import image_stitcher as v3
from processamento.unificacao_imagens.auto_merge.nivel1 import read_level1


def _source_files(chapter: Path, intervals: list[dict]) -> list[str]:
    pages, cursor = [], 0
    try:
        for path in v3.list_pages(chapter):
            with Image.open(path) as image:
                end = cursor + image.height
            pages.append((path.name, cursor, end))
            cursor = end
    except OSError:
        return []
    names = {
        name for interval in intervals for name, start, end in pages
        if end > interval["global_start"] and start < interval["global_end"]
    }
    return sorted(names, key=lambda name: v3.natural_key(Path(name)))


def existing_level1_result(manga: Path, chapter_name: str) -> dict:
    """Return prior work as recorded; never rerun or alter its stage files."""
    chapter = manga / "IMG" / chapter_name
    record = read_level1(manga, chapter_name)
    if record.status != "recorded":
        raise FileExistsError(
            f"{chapter_name}: estágio existente sem manifesto Nível I válido; revisar antes de nova execução."
        )
    data = record.data or {}
    artifacts = data["artifacts"]
    saved_files = [item["file"] for item in artifacts if item["exists"]]
    residuals = data["residuals"]
    missing = len(saved_files) != len(artifacts)
    pending_files = _source_files(chapter, residuals)
    invalid_complete = data["kind"] == "complete" and not residuals
    status = "failed" if missing or invalid_complete else "partial" if residuals and saved_files else "unresolved"
    result = {
        "chapter": chapter_name,
        "status": status,
        "artifacts": len(saved_files),
        "saved_files": saved_files,
        "pending_files": pending_files,
        "pending_segments": len(residuals),
        "residuals": residuals,
        "reason_codes": data.get("reason_codes", []),
        "next_stage": "Auto-Merge Nível II" if residuals else "—",
        "existing_record": True,
    }
    if missing or invalid_complete:
        result["error"] = (
            "O manifesto existente referencia artefatos ausentes." if missing
            else "Estágio completo sem MERGE oficial; revisar antes de nova execução."
        )
    return result
