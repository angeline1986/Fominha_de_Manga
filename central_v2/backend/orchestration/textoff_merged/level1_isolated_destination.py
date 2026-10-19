"""Restricted context for Level-I target-only tests, never enabled by environment or UI."""
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

from .write_destination import planned_write_chapter

_ACTIVE = ContextVar("level1_isolated_write", default=None)


@contextmanager
def numbered_level1_in_isolated_workspace(manga: Path):
    """Opt in for a marked *temporary* workspace; not a production flag."""
    manga = Path(manga)
    root = manga.resolve(strict=True)
    marker = root / ".textoff-isolated-workspace"
    if manga.is_symlink() or not marker.is_file() or marker.is_symlink():
        raise ValueError("Workspace isolado nao autorizado.")
    if not any(part.startswith("textoff04c-") for part in root.parts):
        raise ValueError("Execute apenas em workspace temporario textoff04c-.")
    token = _ACTIVE.set(root)
    try:
        yield
    finally:
        _ACTIVE.reset(token)


def isolated_level1_target(manga: Path, chapter: str):
    """None outside an isolated context; numbered write path within it."""
    active = _ACTIVE.get()
    if active is None:
        return None
    if Path(manga).resolve(strict=True) != active:
        raise ValueError("Obra diferente do workspace isolado.")
    return planned_write_chapter(Path(manga), "auto_cleaner", chapter, preview_target=True)
