from pathlib import Path
STAGE = Path("FLUXO_SECUNDARIO") / "04_TEXTO_OFF" / "BUBBLE_SOMMELIER"
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
def merge_dir(manga: Path, chapter: str) -> Path:
    return manga / "FLUXO_SECUNDARIO" / "02_MERGE" / chapter
def manifest(manga: Path, chapter: str) -> Path:
    return manga / STAGE / chapter / "sommelier-report.json"
def images(folder: Path) -> list[Path]:
    if not folder.is_dir(): return []
    return sorted((p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTS), key=lambda p:p.name)
def validate_selection(manga: Path, chapters: object) -> list[str]:
    if not isinstance(chapters, list) or not chapters: raise ValueError("Selecione ao menos um capítulo.")
    result=[]
    for raw in chapters:
        chapter=str(raw)
        if Path(chapter).name != chapter or not images(merge_dir(manga,chapter)):
            raise ValueError(f"Capítulo {chapter} não possui MERGEs válidos.")
        if chapter not in result: result.append(chapter)
    return result
