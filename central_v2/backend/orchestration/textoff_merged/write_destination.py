"""Resolve TextOff write destinations without creating files."""
from pathlib import Path

from . import artifact_migration as migration

_ALLOWED = {"PERSISTENT_STAGE", "CONSOLIDATED_OUTPUT_INTERMEDIATE"}


def planned_write_chapter(manga: Path, stage_id: str, chapter: str, *,
                          preview_target: bool = False) -> Path:
    """Use numbered output in single-write mode; retain dual-write test planning."""
    if type(preview_target) is not bool:
        raise TypeError("preview_target deve ser booleano")
    if not isinstance(stage_id, str) or not stage_id:
        raise ValueError("stage_id inválido")
    if not isinstance(chapter, str) or not chapter or chapter in {".", ".."}:
        raise ValueError("capítulo inválido")
    if Path(chapter).name != chapter or "/" in chapter or "\\" in chapter:
        raise ValueError("capítulo inválido")
    registry = migration._read_registry(migration.REGISTRY_PATH)
    single_write = (registry.get("migration_mode") == "single_write_target"
                    and registry.get("read_authority") == "target"
                    and registry.get("dual_write_enabled") is False)
    if (registry.get("migration_mode") != "dual_write"
            or registry.get("dual_write_enabled") is not True) and not single_write:
        raise ValueError("Modo operacional não suportado no Patch 04A")
    entry = next((item for item in registry["stages"]
                  if item.get("stage_id") == stage_id), None)
    if (entry is None or (entry.get("dual_write") is not True and not single_write)
            or (single_write and (entry.get("dual_write") is not False
                                  or entry.get("read_authority") != "target"))
            or entry.get("classification") not in _ALLOWED):
        raise ValueError(f"Estágio não elegível: {stage_id}")
    relative = entry.get("target_path" if preview_target or single_write else "legacy_path")
    if not isinstance(relative, str) or not relative:
        raise ValueError("Caminho de saída inválido")
    safe = migration._chapter_path(Path(manga), relative, chapter)
    return Path(manga) / migration.TEXT_OFF_ROOT / relative / chapter
