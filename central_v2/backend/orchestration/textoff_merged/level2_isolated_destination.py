"""Destino exclusivo do Nível II, limitado a workspace temporário autorizado."""
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

from .write_destination import planned_write_chapter

_ACTIVE = ContextVar("textoff04h_workspace", default=None)


@contextmanager
def numbered_level2_in_isolated_workspace(manga: Path):
    manga = Path(manga)
    resolved = manga.resolve(strict=True)
    marker = resolved / ".textoff-isolated-workspace"
    if manga.is_symlink() or not marker.is_file() or marker.is_symlink():
        raise ValueError("Workspace isolado 04H não autorizado.")
    if not any(part.startswith("textoff04h-") for part in resolved.parts):
        raise ValueError("Workspace deve estar em diretório temporário textoff04h-.")
    token = _ACTIVE.set(resolved)
    try:
        yield
    finally:
        _ACTIVE.reset(token)


def isolated_level2_target(manga: Path, chapter: str):
    active = _ACTIVE.get()
    if active is None:
        return None
    if Path(manga).resolve(strict=True) != active:
        raise ValueError("Obra diferente do workspace isolado 04H.")
    return planned_write_chapter(
        Path(manga), "auto_cleaner_transparencia_basica",
        chapter, preview_target=True,
    )
