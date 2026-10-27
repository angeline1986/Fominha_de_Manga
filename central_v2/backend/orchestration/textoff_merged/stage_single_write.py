"""Single-write destinations with read compatibility for unmigrated chapters."""
from pathlib import Path

from . import artifact_migration as migration


def entry_for(stage: str) -> dict | None:
    registry = migration._read_registry(migration.REGISTRY_PATH)
    if registry.get("migration_mode") != "single_write_target":
        return None
    if (registry.get("read_authority") != "target"
            or registry.get("dual_write_enabled") is not False
            or registry.get("legacy_read_enabled") is not True
            or registry.get("new_read_enabled") is not True):
        raise ValueError("Contrato de gravação única inválido")
    entry = next((item for item in registry["stages"]
                  if item.get("legacy_path") == stage
                  and item.get("classification") in {
                      "PERSISTENT_STAGE", "CONSOLIDATED_OUTPUT_INTERMEDIATE"
                  }), None)
    if entry is not None and (entry.get("read_authority") != "target"
                              or entry.get("dual_write") is not False):
        raise ValueError(f"Contrato de gravação única inválido: {stage}")
    return entry


def target_root(manga: Path, entry: dict) -> Path:
    relative = entry["target_path"]
    migration._chapter_path(manga, relative, "_validation_")
    current = Path(manga)
    for part in (migration.TEXT_OFF_ROOT / relative).parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"Destino de gravação inválido: {entry['stage_id']}")
    return current


def read_chapter(manga: Path, entry: dict, chapter: str,
                 legacy_alias: str | None = None) -> Path:
    migration._chapter_path(manga, entry["target_path"], chapter)
    target = target_root(manga, entry) / chapter
    if target.is_symlink() or (target.exists() and not target.is_dir()):
        raise migration.ArtifactAuthorityUnavailable(
            f"Destino de leitura inválido: {entry['stage_id']} / {chapter}")
    if target.is_dir():
        return target
    migration._chapter_path(manga, entry["legacy_path"], chapter)
    legacy = Path(manga) / migration.TEXT_OFF_ROOT / entry["legacy_path"] / chapter
    if legacy.is_symlink() or (legacy.exists() and not legacy.is_dir()):
        raise migration.ArtifactAuthorityUnavailable(
            f"Legado de leitura inválido: {entry['stage_id']} / {chapter}")
    if legacy.is_dir():
        return legacy
    if legacy_alias:
        migration._chapter_path(manga, legacy_alias, chapter)
        alias = Path(manga) / migration.TEXT_OFF_ROOT / legacy_alias / chapter
        if alias.is_dir() and not alias.is_symlink():
            return alias
    return target
