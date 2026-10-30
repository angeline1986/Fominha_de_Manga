"""Canonical TextOff Merged output names and legacy read compatibility."""
from pathlib import Path
import os
import json
from contextlib import contextmanager
from contextvars import ContextVar
from central_v2.backend.state.work_layout import textoff_root

LEVEL1 = "TO_MERGED_NIVEL_I"
LEVEL2 = "TO_MERGED_NIVEL_II"
LEVEL3 = "TO_MERGED_NIVEL_III"
CONSOLIDATED = "TO_MERGED_CONSOLIDADO"
COMBO_TURBO = "COMBO_TURBO"
_MAPPED = {LEVEL1, LEVEL2, LEVEL3, CONSOLIDATED, "BUBBLE_SOMMELIER"}

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
_paths = ContextVar("textoff_stage_paths", default=None)


def provider_name(manga: Path) -> str:
    """Return the operational provider identity for a source or isolated copy."""
    manga = Path(manga).resolve()
    if manga.parent.name != ".combo-workspace":
        return manga.parent.name
    marker = manga.parent.parent / ".combo-workspace.json"
    data = json.loads(marker.read_text(encoding="utf-8"))
    provider = data.get("provider")
    source = Path(data.get("source", "")).resolve()
    if not isinstance(provider, str) or not provider or source.parent.name != provider:
        raise ValueError("Identidade do provider no workspace isolado é inválida.")
    return provider


def _fingerprint(path: Path):
    try:
        stat = path.stat()
        return stat.st_dev, stat.st_ino, stat.st_mtime_ns, stat.st_ctime_ns
    except OSError:
        return None


@contextmanager
def stage_path_snapshot():
    """Reuse validated stage paths, then verify authority and directory identity."""
    paths = {}
    token = _paths.set(paths)
    try:
        yield
        for (manga, stage, chapter, read_legacy), (path, identity) in paths.items():
            current = _resolve_stage_chapter(manga, stage, chapter, read_legacy=read_legacy)
            if current != path or _fingerprint(current) != identity:
                raise OSError("Caminho de estágio alterado durante a consulta.")
    finally:
        _paths.reset(token)


def stage_root(manga: Path, stage: str, *, read_legacy: bool = True) -> Path:
    canonical = ALIASES.get(stage, stage)
    from .stage_single_write import entry_for, target_root
    entry = entry_for(canonical) if canonical in _MAPPED else None
    if entry is not None:
        return target_root(manga, entry)
    if canonical == LEVEL1 and os.environ.get("CENTRAL_V2_LEVEL1_NUMBERED") == "1":
        return textoff_root(manga) / "01_AUTO_CLEANER"
    if canonical in PINCEIS:
        return textoff_root(manga) / PINCEIS[canonical]
    current = textoff_root(manga) / canonical
    legacy_name = LEGACY_NAMES.get(canonical)
    legacy = textoff_root(manga) / legacy_name if legacy_name else None
    if read_legacy and not current.exists() and legacy is not None and legacy.exists():
        return legacy
    return current


def stage_chapter(manga: Path, stage: str, chapter: str, *, read_legacy: bool = True) -> Path:
    paths = _paths.get()
    canonical = ALIASES.get(stage, stage)
    if paths is not None and canonical not in PINCEIS:
        key = (Path(manga), stage, chapter, read_legacy)
        if key in paths:
            return paths[key][0]
        result = _resolve_stage_chapter(manga, stage, chapter, read_legacy=read_legacy)
        paths[key] = (result, _fingerprint(result))
        return result
    return _resolve_stage_chapter(manga, stage, chapter, read_legacy=read_legacy)


def _resolve_stage_chapter(manga: Path, stage: str, chapter: str, *, read_legacy: bool = True) -> Path:
    canonical = ALIASES.get(stage, stage)
    from .stage_single_write import entry_for, read_chapter
    entry = entry_for(canonical) if canonical in _MAPPED else None
    if entry is not None:
        if read_legacy:
            return read_chapter(manga, entry, chapter, LEGACY_NAMES.get(canonical))
        return stage_root(manga, canonical, read_legacy=False) / chapter
    if canonical == LEVEL1 and os.environ.get("CENTRAL_V2_LEVEL1_NUMBERED") == "1":
        return stage_root(manga, LEVEL1, read_legacy=False) / chapter
    if canonical in PINCEIS:
        target = stage_root(manga, canonical, read_legacy=False) / chapter
        legacy = textoff_root(manga) / canonical / chapter
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
