"""Canonical TextOff Merged output names and legacy read compatibility."""
from pathlib import Path

LEVEL1 = "TO_MERGED_NIVEL_I"
LEVEL2 = "TO_MERGED_NIVEL_II"
LEVEL3 = "TO_MERGED_NIVEL_III"
CONSOLIDATED = "TO_MERGED_CONSOLIDADO"

LEGACY_NAMES = {
    LEVEL1: "MERGED_NIVEL_I",
    LEVEL2: "MERGED_NIVEL_II",
    LEVEL3: "MERGED_NIVEL_III",
}
ALIASES = {legacy: canonical for canonical, legacy in LEGACY_NAMES.items()}


def stage_root(manga: Path, stage: str, *, read_legacy: bool = True) -> Path:
    canonical = ALIASES.get(stage, stage)
    current = manga / "FLUXO_SECUNDARIO" / "04_TEXTO_OFF" / canonical
    legacy_name = LEGACY_NAMES.get(canonical)
    legacy = manga / "FLUXO_SECUNDARIO" / "04_TEXTO_OFF" / legacy_name if legacy_name else None
    if read_legacy and not current.exists() and legacy is not None and legacy.exists():
        return legacy
    return current


def stage_chapter(manga: Path, stage: str, chapter: str, *, read_legacy: bool = True) -> Path:
    return stage_root(manga, stage, read_legacy=read_legacy) / chapter
