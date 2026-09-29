"""Stable per-chapter artifact paths for TextOff Merged V2 stages."""
from pathlib import Path

DIRECTORIES = {"clean": "clean", "mask": "mask", "json": "json"}


def artifact_ref(kind: str, name: str) -> str:
    """Return a safe manifest reference such as ``clean/page_clean.png``."""
    if kind not in DIRECTORIES or Path(name).name != name or name in {"", ".", ".."}:
        raise ValueError("Referência de artefato inválida.")
    return f"{DIRECTORIES[kind]}/{name}"


def artifact_file(chapter_dir: Path, reference: object, kind: str) -> Path | None:
    """Resolve new references and pre-layout basenames without path traversal."""
    if kind not in DIRECTORIES or not isinstance(reference, str):
        return None
    path = Path(reference)
    if path.is_absolute() or ".." in path.parts:
        return None
    if len(path.parts) == 2 and path.parts[0] == DIRECTORIES[kind]:
        candidate = chapter_dir / path
        if not candidate.is_file():
            candidate = chapter_dir / path.name
    elif len(path.parts) == 1 and path.name:
        candidate = chapter_dir / DIRECTORIES[kind] / path.name
        if not candidate.is_file():
            candidate = chapter_dir / path.name
    else:
        return None
    return candidate if candidate.is_file() else None


def json_file(chapter_dir: Path, name: str) -> Path:
    """Find a JSON artifact in the organized layout or the previous flat layout."""
    organized = chapter_dir / DIRECTORIES["json"] / name
    return organized if organized.is_file() else chapter_dir / name


def prepare_artifact_dirs(chapter_dir: Path) -> None:
    for directory in DIRECTORIES.values():
        (chapter_dir / directory).mkdir(parents=True, exist_ok=True)
