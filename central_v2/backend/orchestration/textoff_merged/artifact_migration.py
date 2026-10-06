"""Registry-driven shadow copies for persistent TextOff artifact stages."""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import shutil
import tempfile
import uuid


REGISTRY_PATH = Path(__file__).with_name("artifact-migration-registry.json")
TEXT_OFF_ROOT = Path("FLUXO_SECUNDARIO") / "04_TEXTO_OFF"
logger = logging.getLogger(__name__)


class ArtifactAuthorityUnavailable(FileNotFoundError):
    """The registry-selected artifact tree cannot serve this chapter."""


class ArtifactMirrorError(RuntimeError):
    """A legacy artifact was published but its migration shadow was not."""

    def __init__(self, stage_id: str, legacy: Path | None, target: Path | None,
                 detail: str):
        self.stage_id = stage_id
        self.legacy = legacy
        self.target = target
        super().__init__(
            f"DUAL_WRITE_MIRROR_FAILED stage={stage_id} legacy={legacy} "
            f"target={target}: {detail}"
        )


def mirror_stage_chapter(manga: Path, stage_id: str, chapter: str) -> bool:
    """Mirror one committed chapter tree using paths declared by the registry."""
    legacy = target = None
    try:
        registry = _read_registry(REGISTRY_PATH)
        if (registry.get("migration_mode") != "dual_write"
                or registry.get("dual_write_enabled") is not True):
            return False
        entry = next((stage for stage in registry.get("stages", [])
                      if stage.get("stage_id") == stage_id), None)
        if entry is None:
            raise ValueError(f"Estágio ausente do registry: {stage_id}")
        if entry.get("dual_write") is not True:
            return False
        if (entry.get("classification") not in {"PERSISTENT_STAGE", "CONSOLIDATED_OUTPUT_INTERMEDIATE"}
                or entry.get("read_authority") not in {"legacy", "target"}):
            raise ValueError(f"Contrato inválido para dual-write: {stage_id}")
        if (not isinstance(chapter, str) or chapter in {"", ".", ".."}
                or Path(chapter).name != chapter or "/" in chapter or "\\" in chapter):
            raise ValueError("Identificador de capítulo inválido.")
        legacy_path = entry.get("legacy_path")
        target_path = entry.get("target_path")
        if not isinstance(legacy_path, str) or not isinstance(target_path, str):
            raise ValueError(f"Caminhos de persistência inválidos para {stage_id}.")
        legacy = _chapter_path(manga, legacy_path, chapter)
        target = _chapter_path(manga, target_path, chapter)
        _mirror_tree(legacy, target)
        return True
    except ArtifactMirrorError:
        raise
    except Exception as exc:
        raise ArtifactMirrorError(stage_id, legacy, target, str(exc)) from exc


def _read_registry(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("stages"), list):
        raise ValueError("Registry de migração inválido.")
    return payload


def resolve_authoritative_stage_chapter(
    manga: Path, stage_id: str, chapter: str, *, registry_path: Path | None = None,
) -> Path:
    """Resolve only the registry-selected side; never substitute the other side."""
    registry_path = Path(registry_path) if registry_path is not None else REGISTRY_PATH
    if (not isinstance(chapter, str) or chapter in {"", ".", ".."}
            or Path(chapter).name != chapter or "/" in chapter or "\\" in chapter):
        raise ValueError("Identificador de capítulo inválido.")
    registry = _read_registry(registry_path)
    entry = next((item for item in registry["stages"]
                  if item.get("stage_id") == stage_id), None)
    if entry is None or entry.get("dual_write") is not True:
        raise ValueError(f"Stage sem mapping persistente: {stage_id}")
    authority = registry.get("read_authority")
    if (authority not in {"legacy", "target"}
            or entry.get("read_authority") != authority
            or registry.get("legacy_read_enabled") is not True
            or registry.get("new_read_enabled") is not True
            or registry.get("dual_write_enabled") is not True):
        raise ValueError(f"Contrato de autoridade inválido para {stage_id}")
    relative = entry.get(f"{authority}_path")
    if not isinstance(relative, str):
        raise ValueError(f"Caminho {authority} inválido para {stage_id}")
    _chapter_path(manga, relative, chapter)  # validate containment before preserving caller path form
    path = Path(manga) / TEXT_OFF_ROOT / relative / chapter
    if authority == "target" and (path.is_symlink() or not path.is_dir()):
        status = "MISSING_TARGET" if not path.exists() else "INVALID_TARGET"
        message = (f"AUTHORITY_UNAVAILABLE authority=target stage={stage_id} "
                   f"chapter={chapter} status={status} target={path}")
        logger.error(message)
        raise ArtifactAuthorityUnavailable(message)
    return path


def _chapter_path(manga: Path, relative_stage: str, chapter: str) -> Path:
    relative = Path(relative_stage)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"Caminho de estágio fora da obra: {relative_stage}")
    root = manga.resolve()
    path = root / TEXT_OFF_ROOT / relative / chapter
    if not path.resolve().is_relative_to(root):
        raise ValueError(f"Caminho de estágio fora da obra: {relative_stage}")
    return path


def _mirror_tree(legacy: Path, target: Path) -> None:
    if legacy == target or not legacy.is_dir() or legacy.is_symlink():
        raise FileNotFoundError(f"Árvore legada ausente ou inválida: {legacy}")
    if target.exists() and (not target.is_dir() or target.is_symlink()):
        raise ValueError(f"Destino shadow não é um diretório válido: {target}")
    if any(path.is_symlink() for path in legacy.rglob("*")):
        raise ValueError(f"A árvore legada contém symlinks: {legacy}")

    target.parent.mkdir(parents=True, exist_ok=True)
    staged = Path(tempfile.mkdtemp(prefix=f".{target.name}.shadow-", dir=target.parent))
    staged.rmdir()
    backup = target.parent / f".{target.name}.backup-{uuid.uuid4().hex}"
    moved_old_target = False
    try:
        shutil.copytree(legacy, staged, copy_function=shutil.copy2)
        if target.exists():
            os.replace(target, backup)
            moved_old_target = True
        try:
            os.replace(staged, target)
        except Exception:
            if moved_old_target and backup.exists() and not target.exists():
                os.replace(backup, target)
                moved_old_target = False
            raise
        if moved_old_target:
            shutil.rmtree(backup, ignore_errors=True)
    finally:
        if staged.exists():
            shutil.rmtree(staged, ignore_errors=True)
