"""Bind a Sólidos preview to one verified source and official final page."""
from pathlib import Path

from central_v2.backend.orchestration.textoff_special.artifacts import sha256
from .laboratorio_final_target import final_target


def solid_target(manga: Path, meta: dict) -> tuple[str, str]:
    manga = manga.resolve()
    chapter, page, digest = (meta.get(key) for key in
                             ("chapter", "page", "source_sha256"))
    if (not isinstance(chapter, str) or not isinstance(page, str)
            or Path(chapter).name != chapter or Path(page).name != page
            or chapter in {"", ".", ".."} or page in {"", ".", ".."}):
        raise ValueError("Origem do Sólidos inválida.")
    source = {"chapter": chapter, "filename": page}
    recorded = meta.get("source_path")
    if recorded is not None:
        if (not isinstance(recorded, str) or not recorded
                or Path(recorded).is_absolute()
                or any(part in {".", ".."} for part in Path(recorded).parts)):
            raise ValueError("Caminho da origem Sólidos inválido.")
        path = (manga / recorded).resolve()
        if (not path.is_relative_to(manga)
                or not path.is_file() or path.name != page or sha256(path) != digest):
            raise ValueError("Origem do Sólidos mudou ou está indisponível.")
        return final_target(manga, path, source)
    targets = set()
    for entry in manga.rglob(page):
        path = entry.resolve()
        if (path.is_relative_to(manga) and path.is_file()
                and path.name == page and sha256(path) == digest):
            targets.add(final_target(manga, path, source))
    if len(targets) != 1:
        raise ValueError("Origem histórica do Sólidos não identifica uma página final única.")
    return targets.pop()
