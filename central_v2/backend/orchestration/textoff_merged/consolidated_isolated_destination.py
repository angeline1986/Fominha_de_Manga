"""Opt-in Consolidado target-only, authorized only inside a temporary test workspace."""
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

from .write_destination import planned_write_chapter

_ACTIVE = ContextVar('consolidated_target_only_workspace', default=None)


@contextmanager
def numbered_consolidated_in_isolated_workspace(manga: Path):
    root = Path(manga).resolve(strict=True)
    marker = root / '.textoff-isolated-workspace'
    if (Path(manga).is_symlink() or not marker.is_file() or marker.is_symlink()
            or not any(p.startswith('textoff04e-') for p in root.parts)):
        raise ValueError('Consolidado numerado permitido apenas em workspace temporario 04E.')
    token = _ACTIVE.set(root)
    try:
        yield
    finally:
        _ACTIVE.reset(token)


def isolated_consolidated_target(manga: Path, chapter: str):
    root = _ACTIVE.get()
    if root is None:
        return None
    if Path(manga).resolve(strict=True) != root:
        raise ValueError('Obra diferente do workspace isolado.')
    return planned_write_chapter(Path(manga), 'mapear_input_consolidado', chapter,
                                 preview_target=True)
