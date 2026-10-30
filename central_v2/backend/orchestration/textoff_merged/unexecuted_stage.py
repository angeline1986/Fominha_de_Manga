"""Non-mutating check for stages absent on both migration sides."""
from pathlib import Path
from central_v2.backend.state.work_layout import textoff_root


def both_absent(manga: Path, legacy: str, target: str, chapter: str) -> bool:
    root = textoff_root(manga)
    for side in (legacy, target):
        path = root / side / chapter
        if path.exists() or path.is_symlink():
            return False
    return True
