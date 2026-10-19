"""Explicit, context-scoped target-only writes for isolated Mapear tests."""
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

from .write_destination import planned_write_chapter

_ACTIVE = ContextVar('textoff04f_mapear_workspace', default=None)


@contextmanager
def numbered_mapear_in_isolated_workspace(manga: Path):
    root = Path(manga).resolve(strict=True)
    marker = root / '.textoff-isolated-workspace'
    if (Path(manga).is_symlink() or not marker.is_file() or marker.is_symlink()
            or not any(part.startswith('textoff04f-') for part in root.parts)):
        raise ValueError('Mapear: workspace temporario nao autorizado.')
    token = _ACTIVE.set(root)
    try:
        yield
    finally:
        _ACTIVE.reset(token)


def isolated_mapear_target(manga: Path, chapter: str):
    active = _ACTIVE.get()
    if active is None:
        return None
    if Path(manga).resolve(strict=True) != active:
        raise ValueError('Mapear: obra diferente do workspace isolado.')
    return planned_write_chapter(Path(manga), 'mapear', chapter, preview_target=True)
