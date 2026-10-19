"""Non-mutating check for stages absent on both migration sides."""
from pathlib import Path


def both_absent(manga: Path, legacy: str, target: str, chapter: str) -> bool:
    root = Path(manga) / "FLUXO_SECUNDARIO" / "04_TEXTO_OFF"
    for side in (legacy, target):
        path = root / side / chapter
        if path.exists() or path.is_symlink():
            return False
    return True
