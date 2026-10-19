"""Opt-in write destination restricted to temporary Bubble Sommelier tests."""
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

from central_v2.backend.orchestration.textoff_merged.write_destination import planned_write_chapter

_ACTIVE = ContextVar("sommelier_04g_isolated", default=None)


@contextmanager
def numbered_sommelier_in_isolated_workspace(manga: Path):
    root = Path(manga).resolve(strict=True)
    marker = root / ".textoff-isolated-workspace"
    if (Path(manga).is_symlink() or not marker.is_file() or marker.is_symlink()
            or not any(part.startswith("textoff04g-") for part in root.parts)):
        raise ValueError("Workspace temporario 04G nao autorizado")
    token = _ACTIVE.set(root)
    try:
        yield
    finally:
        _ACTIVE.reset(token)


def isolated_sommelier_target(manga: Path, chapter: str):
    root = _ACTIVE.get()
    if root is None:
        return None
    if Path(manga).resolve(strict=True) != root:
        raise ValueError("Obra fora do workspace 04G")
    return planned_write_chapter(Path(manga), "bubble_sommelier", chapter, preview_target=True)
