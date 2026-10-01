"""Resolve manifest-bound before/after pairs; no image promotion or writes."""
from pathlib import Path
import hashlib

from .artifact_paths import artifact_file
from .manifests import (
    _listing_merge_artifacts, _manifest_matches_merge, _stage_manifest,
    _stage_manifest_sha256,
)
from .stages import LEVEL1, LEVEL2, stage_chapter
from .consolidated import _valid_level2
from .overview import current_preview_records
from central_v2.backend.orchestration.textoff_special.artifacts import contained_file, sha256
from central_v2.backend.orchestration.textoff_special.catalog import STAGING_ROOT


def comparison_pairs(manga: Path, chapter: str, step: str) -> list[dict]:
    if step not in {"1", "2", "3", "4"}:
        raise ValueError("Passo inválido.")
    if not chapter or chapter in {".", ".."} or Path(chapter).name != chapter:
        raise ValueError("Capítulo inválido.")
    level1 = _stage_manifest(manga, LEVEL1, chapter)
    if not _manifest_matches_merge(level1, manga, chapter):
        return []
    folder = stage_chapter(manga, LEVEL1, chapter)
    originals = _listing_merge_artifacts(manga / "IMG" / chapter)
    if step in {"3", "4"}:
        return _preview_pairs(manga, chapter, step)
    level2, level2_folder, _ = _valid_level2(
        manga, chapter, level1, _stage_manifest_sha256(manga, LEVEL1, chapter)
    ) if step == "2" else (None, None, None)
    if step == "2" and level2 is None:
        return []
    pairs = []
    for original in originals:
        name = original.stem + "_clean" + original.suffix
        clean = artifact_file(folder, name, "clean")
        if clean is None:
            continue
        before, after = original, clean
        if step == "2":
            if original.name not in level2.get("candidate_source_artifacts", []):
                continue
            # Unchanged candidate pages retain their Level I artifact.
            before = clean
            after = artifact_file(level2_folder, name, "clean") or clean
        if all(path.resolve().is_relative_to(manga.resolve()) for path in (before, after)):
            pairs.append({"name": original.name, "before": before, "after": after})
    return pairs


def _preview_pairs(manga: Path, chapter: str, step: str) -> list[dict]:
    latest = {}
    for key, manifest in current_preview_records(manga):
        source = manifest["source"]
        if key != f"ac{step}" or source["chapter"] != chapter:
            continue
        name = source["filename"]
        if manifest.get("finished_at", "") >= latest.get(name, {}).get("finished_at", ""):
            latest[name] = manifest
    pairs = []
    for name, manifest in sorted(latest.items()):
        run_id = manifest.get("run_id", "")
        if not run_id or Path(run_id).name != run_id or run_id in {".", ".."}:
            continue
        try:
            folder = STAGING_ROOT / run_id
            before = contained_file(folder, "input/source.png")
            if sha256(before) != manifest["source"]["sha256"]:
                continue
            after = contained_file(folder, manifest["result_file"])
            pairs.append({"name": name, "before": before, "after": after})
        except (OSError, ValueError):
            continue
    return pairs


def pair_version(pair: dict) -> str:
    signature = []
    for side in ("before", "after"):
        path = pair[side]
        info = path.stat()
        signature.append(f"{path.resolve()}:{info.st_size}:{info.st_mtime_ns}")
    return hashlib.sha256("|".join(signature).encode()).hexdigest()
