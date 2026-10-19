"""Public compatibility facade for consolidated TextOff selection and promotion."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import tempfile
import uuid

from .artifact_paths import artifact_ref, prepare_artifact_dirs
from .artifact_migration import mirror_stage_chapter, ArtifactAuthorityUnavailable
from .consolidated_isolated_destination import isolated_consolidated_target
from .unexecuted_stage import both_absent
from .consolidated_selection import (
    _artifact_map, _combo_selections, _select_artifacts, _selected_pages_match,
    _selection_is_current,
)
from .level2_legacy_validation import (
    _changed_source_set, _source_from_clean, _valid_legacy_level2,
)
from .level2_result_validation import _valid_level2_page_results
from .consolidated_level2_validation import _valid_level2, _valid_level2_unchecked
from .manifests import _manifest_matches_merge, _stage_manifest, _stage_manifest_sha256
from .level2_vision import ALGORITHM as LEVEL2_ALGORITHM
from .stages import COMBO_TURBO, CONSOLIDATED, LEVEL1, LEVEL2, stage_chapter

ALGORITHM = "textoff_merged_consolidated_level2_over_level1_v1"


def rebuild_consolidated(manga: Path, chapter: str) -> dict:
    level1 = _stage_manifest(manga, LEVEL1, chapter)
    if not _manifest_matches_merge(level1, manga, chapter):
        raise ValueError(f"Nível I inválido para consolidar Cap. {chapter}.")
    level1_hash = _stage_manifest_sha256(manga, LEVEL1, chapter)
    source_names = level1["source_artifacts"]
    level1_dir = stage_chapter(manga, LEVEL1, chapter)
    level2, level2_dir, level2_hash = _valid_level2(manga, chapter, level1, level1_hash)
    selected = _select_artifacts(source_names, level1, level1_dir, level2, level2_dir)
    combo_hash, combo_rows = _combo_selections(manga, chapter, source_names)
    selected = [(combo_rows.get(name, (path, stage))[0],
                 COMBO_TURBO if name in combo_rows else stage)
                for name, (path, stage) in zip(source_names, selected)]
    isolated_target = isolated_consolidated_target(manga, chapter)
    target = isolated_target or stage_chapter(manga, CONSOLIDATED, chapter, read_legacy=False)
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f".consolidate-{chapter}-", dir=target.parent) as temp:
        staged = Path(temp) / "stage"
        prepare_artifact_dirs(staged)
        selections = []
        for source_name, (path, source_stage) in zip(source_names, selected):
            digest = _sha256(path)
            destination_name = Path(source_name).stem + "_clean" + Path(source_name).suffix
            if source_stage == LEVEL2:
                destination = staged / artifact_ref("clean", destination_name)
                shutil.copy2(path, destination)
                if _sha256(destination) != digest:
                    raise IOError(f"Falha ao validar a cópia consolidada de {source_name}.")
            item = {"source": source_name, "selected_from": source_stage,
                    "artifact": artifact_ref("clean", destination_name), "sha256": digest}
            if source_stage == COMBO_TURBO:
                item["source_artifact"] = combo_rows[source_name][1]
            selections.append(item)
        manifest = {
            "schema_version": 1, "algorithm": ALGORITHM,
            "source_stage": CONSOLIDATED, "integrity_ok": True,
            "source_artifacts": source_names,
            "source_level1_manifest_sha256": level1_hash,
            "source_level2_manifest_sha256": level2_hash,
            "source_combo_manifest_sha256": combo_hash,
            "clean_artifacts": [item["artifact"] for item in selections],
            "outputs_total": len(source_names), "selections": selections,
        }
        (staged / "json/clean-manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        promote_stage(staged, target)
    if isolated_target is None:
        mirror_stage_chapter(manga, "mapear_input_consolidado", chapter)
    return {"chapter": chapter, "outputs": len(source_names),
            "level2_outputs_used": sum(item["selected_from"] == LEVEL2 for item in selections)}


def consolidated_is_current(manga: Path, chapter: str) -> bool:
    if both_absent(manga, "TO_MERGED_CONSOLIDADO", "02_MAPEAR/INPUT_CONSOLIDADO", chapter):
        return False
    folder = stage_chapter(manga, CONSOLIDATED, chapter)
    try:
        manifest = json.loads((folder / "json/clean-manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return False
    level1 = _stage_manifest(manga, LEVEL1, chapter)
    level1_hash = _stage_manifest_sha256(manga, LEVEL1, chapter)
    if (manifest.get("algorithm") != ALGORITHM or not _manifest_matches_merge(level1, manga, chapter)
            or manifest.get("source_level1_manifest_sha256") != level1_hash
            or manifest.get("source_artifacts") != level1.get("source_artifacts")):
        return False
    level2, _, level2_hash = _valid_level2(manga, chapter, level1, level1_hash)
    if manifest.get("source_level2_manifest_sha256") != level2_hash:
        return False
    try:
        combo_hash, _ = _combo_selections(manga, chapter, level1.get("source_artifacts", []))
    except (OSError, ValueError, TypeError, KeyError):
        return False
    if manifest.get("source_combo_manifest_sha256") != combo_hash:
        return False
    if not _selected_pages_match(manifest, level1, level2, manga, chapter):
        return False
    selections = manifest.get("selections")
    outputs = manifest.get("clean_artifacts")
    if not isinstance(outputs, list) or len(outputs) != len(level1.get("source_artifacts", [])):
        return False
    if not isinstance(selections, list) or len(selections) != len(outputs):
        return False
    return all(_selection_is_current(folder, item, level1, manga, chapter) for item in selections)


def _sha256(path):
    import hashlib
    digest = hashlib.sha256()
    with path.open("rb") as image:
        for block in iter(lambda: image.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def promote_stage(staged, target):
    backup = target.parent / f".{target.name}.backup-{uuid.uuid4().hex}"
    if target.exists():
        os.replace(target, backup)
    try:
        os.replace(staged, target)
    except Exception:
        if backup.exists() and not target.exists():
            os.replace(backup, target)
        raise
    if backup.exists():
        shutil.rmtree(backup, ignore_errors=True)
