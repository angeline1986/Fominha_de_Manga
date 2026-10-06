"""Read-only comparison of legacy and shadow TextOff artifact trees.

STRUCTURAL_MATCH is reserved for a future, explicitly documented allowlist of
deliberately variable files. No current TextOff artifact has that exception,
so this validator emits only MATCH, MISMATCH, missing-side states, or
NOT_APPLICABLE for registry stages outside dual-write scope.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from .artifact_migration import REGISTRY_PATH, TEXT_OFF_ROOT


COMPARISON_STATUSES = frozenset({
    "MATCH",
    "STRUCTURAL_MATCH",
    "MISMATCH",
    "MISSING_LEGACY",
    "MISSING_TARGET",
    "NOT_APPLICABLE",
})
_CHUNK_SIZE = 1024 * 1024
_DUAL_WRITE_CLASSIFICATIONS = frozenset({
    "PERSISTENT_STAGE",
    "CONSOLIDATED_OUTPUT_INTERMEDIATE",
})


def validate_stage_chapter(
    manga: Path,
    stage_id: str,
    chapter: str,
    *,
    registry_path: Path = REGISTRY_PATH,
) -> dict:
    """Compare one registry-mapped stage/chapter without changing either tree."""
    registry = _read_registry(registry_path)
    entry = next((stage for stage in registry["stages"]
                  if stage.get("stage_id") == stage_id), None)
    if entry is None:
        raise ValueError(f"Stage ausente do registry: {stage_id}")
    if (registry.get("migration_mode") != "dual_write"
            or registry.get("dual_write_enabled") is not True
            or entry.get("dual_write") is not True
            or entry.get("classification") not in _DUAL_WRITE_CLASSIFICATIONS):
        return {
            "stage": stage_id,
            "chapter": chapter,
            "legacy_path": entry.get("legacy_path"),
            "target_path": entry.get("target_path"),
            "comparison_status": "NOT_APPLICABLE",
            "artifacts": [],
        }
    if entry.get("read_authority") != "legacy":
        raise ValueError(f"Autoridade de leitura inesperada para {stage_id}")
    _validate_chapter(chapter)
    legacy_stage = _safe_relative_stage_path(entry.get("legacy_path"), stage_id)
    target_stage = _safe_relative_stage_path(entry.get("target_path"), stage_id)
    manga_root = Path(manga).resolve()
    legacy_root = _stage_chapter_path(manga_root, legacy_stage, chapter)
    target_root = _stage_chapter_path(manga_root, target_stage, chapter)
    return compare_artifact_trees(
        legacy_root,
        target_root,
        stage=stage_id,
        chapter=chapter,
        legacy_path=(legacy_stage / chapter).as_posix(),
        target_path=(target_stage / chapter).as_posix(),
    )


def compare_artifact_trees(
    legacy_root: Path,
    target_root: Path,
    *,
    stage: str,
    chapter: str,
    legacy_path: str | None = None,
    target_path: str | None = None,
) -> dict:
    """Compare file paths, sizes, and streaming SHA-256 values in two trees."""
    legacy_root = Path(legacy_root)
    target_root = Path(target_root)
    result = {
        "stage": stage,
        "chapter": chapter,
        "legacy_path": legacy_path or str(legacy_root),
        "target_path": target_path or str(target_root),
        "comparison_status": None,
        "artifacts": [],
    }
    legacy_exists = legacy_root.exists() or legacy_root.is_symlink()
    target_exists = target_root.exists() or target_root.is_symlink()
    if not legacy_exists and not target_exists:
        raise FileNotFoundError(
            f"Ambos os artefatos estão ausentes: legacy={legacy_root}, target={target_root}"
        )
    if not legacy_exists:
        result["comparison_status"] = "MISSING_LEGACY"
        return result
    if not target_exists:
        result["comparison_status"] = "MISSING_TARGET"
        return result
    if (legacy_root.is_symlink() or target_root.is_symlink()
            or not legacy_root.is_dir() or not target_root.is_dir()):
        result["artifacts"] = [{
            "artifact": ".",
            "size_legacy": None,
            "size_target": None,
            "sha256_legacy": None,
            "sha256_target": None,
            "comparison_status": "MISMATCH",
        }]
        result["comparison_status"] = "MISMATCH"
        return result

    legacy_entries = _inventory(legacy_root)
    target_entries = _inventory(target_root)
    artifacts = []
    for relative in sorted(legacy_entries.keys() | target_entries.keys()):
        legacy_entry = legacy_entries.get(relative)
        target_entry = target_entries.get(relative)
        if legacy_entry is None or target_entry is None:
            # Directory/file set differences are represented as an artifact mismatch.
            entry = legacy_entry or target_entry
            artifacts.append(_record(
                relative,
                entry.get("size") if legacy_entry else None,
                entry.get("size") if target_entry else None,
                None,
                None,
                "MISMATCH",
            ))
            continue
        if legacy_entry["kind"] != target_entry["kind"]:
            artifacts.append(_record(relative, None, None, None, None, "MISMATCH"))
            continue
        if legacy_entry["kind"] == "directory":
            continue
        if legacy_entry["kind"] != "file":
            artifacts.append(_record(relative, None, None, None, None, "MISMATCH"))
            continue
        legacy_size, legacy_hash = _size_and_sha256(legacy_entry["path"])
        target_size, target_hash = _size_and_sha256(target_entry["path"])
        status = ("MATCH" if legacy_size == target_size and legacy_hash == target_hash
                  else "MISMATCH")
        artifacts.append(_record(
            relative, legacy_size, target_size, legacy_hash, target_hash, status
        ))
    result["artifacts"] = artifacts
    result["comparison_status"] = (
        "MATCH" if all(item["comparison_status"] == "MATCH" for item in artifacts)
        else "MISMATCH"
    )
    return result


def _record(relative: str, size_legacy, size_target, sha256_legacy,
            sha256_target, status: str) -> dict:
    return {
        "artifact": relative,
        "size_legacy": size_legacy,
        "size_target": size_target,
        "sha256_legacy": sha256_legacy,
        "sha256_target": sha256_target,
        "comparison_status": status,
    }


def _inventory(root: Path) -> dict[str, dict]:
    entries = {}

    def visit(directory: Path, relative_directory: Path) -> None:
        with os.scandir(directory) as iterator:
            children = sorted(iterator, key=lambda item: item.name)
        for child in children:
            relative = (relative_directory / child.name).as_posix()
            path = Path(child.path)
            if child.is_symlink():
                entries[relative] = {"kind": "symlink", "path": path}
            elif child.is_dir(follow_symlinks=False):
                entries[relative] = {"kind": "directory", "path": path}
                visit(path, relative_directory / child.name)
            elif child.is_file(follow_symlinks=False):
                entries[relative] = {"kind": "file", "path": path}
            else:
                entries[relative] = {"kind": "special", "path": path}

    visit(root, Path())
    return entries


def _size_and_sha256(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as source:
        while chunk := source.read(_CHUNK_SIZE):
            size += len(chunk)
            digest.update(chunk)
    return size, digest.hexdigest()


def _read_registry(path: Path) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("stages"), list):
        raise ValueError("Registry de migração inválido.")
    return payload


def _validate_chapter(chapter: str) -> None:
    if (not isinstance(chapter, str) or chapter in {"", ".", ".."}
            or Path(chapter).name != chapter or "/" in chapter or "\\" in chapter):
        raise ValueError("Identificador de capítulo inválido.")


def _safe_relative_stage_path(value: object, stage_id: str) -> Path:
    if not isinstance(value, str):
        raise ValueError(f"Caminho do registry ausente para {stage_id}")
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        raise ValueError(f"Caminho inseguro no registry para {stage_id}: {value}")
    return relative


def _stage_chapter_path(manga_root: Path, stage: Path, chapter: str) -> Path:
    candidate = manga_root / TEXT_OFF_ROOT / stage / chapter
    if not candidate.resolve().is_relative_to(manga_root):
        raise ValueError(f"Caminho de stage fora da obra: {stage}/{chapter}")
    return candidate
