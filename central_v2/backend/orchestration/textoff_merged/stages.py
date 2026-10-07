"""Canonical TextOff Merged output names and legacy read compatibility."""
from pathlib import Path
import os

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
PINCEIS = {
    "PINCEL_DEGRADE": "06_PINCEL/DEGRADE",
    "PINCEL_ARTISTICO": "06_PINCEL/ARTISTICO",
    "PINCEL_SUAVE": "06_PINCEL/SUAVE",
    "CONSOLIDADO_FINAL": "07_CONSOLIDADO_FINAL",
}


def stage_root(manga: Path, stage: str, *, read_legacy: bool = True) -> Path:
    canonical = ALIASES.get(stage, stage)
    if canonical in PINCEIS:
        return manga / "FLUXO_SECUNDARIO" / "04_TEXTO_OFF" / PINCEIS[canonical]
    current = manga / "FLUXO_SECUNDARIO" / "04_TEXTO_OFF" / canonical
    legacy_name = LEGACY_NAMES.get(canonical)
    legacy = manga / "FLUXO_SECUNDARIO" / "04_TEXTO_OFF" / legacy_name if legacy_name else None
    if read_legacy and not current.exists() and legacy is not None and legacy.exists():
        return legacy
    return current


def stage_chapter(manga: Path, stage: str, chapter: str, *, read_legacy: bool = True) -> Path:
    canonical = ALIASES.get(stage, stage)
    if canonical in PINCEIS:
        target = stage_root(manga, canonical, read_legacy=False) / chapter
        legacy = manga / "FLUXO_SECUNDARIO" / "04_TEXTO_OFF" / canonical / chapter
        if not target.exists() and legacy.is_dir() and not legacy.is_symlink():
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(legacy, target)
        return target
    if read_legacy:
        from .artifact_migration import resolve_authoritative_stage_chapter
        from .artifact_migration import _read_registry
        from .artifact_migration import REGISTRY_PATH
        registry = _read_registry(REGISTRY_PATH)
        entry = next((item for item in registry["stages"]
                      if item.get("legacy_path") == canonical), None)
        if entry is not None and entry.get("dual_write") is True:
            selected = resolve_authoritative_stage_chapter(
                manga, entry["stage_id"], chapter
            )
            if entry.get("read_authority") == "legacy":
                legacy_name = LEGACY_NAMES.get(canonical)
                alias = selected.parent.parent / legacy_name if legacy_name else None
                if not selected.exists() and alias is not None and alias.exists():
                    return alias / chapter
            return selected
    return stage_root(manga, stage, read_legacy=read_legacy) / chapter
