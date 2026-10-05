"""Resolve manifest-bound before/after pairs; no image promotion or writes."""
from pathlib import Path
import hashlib

from .artifact_paths import artifact_file
from .manifests import (
    _listing_merge_artifacts, _manifest_matches_merge, _stage_manifest,
    _stage_manifest_sha256,
)
from .stages import LEVEL1, LEVEL2, stage_chapter
from .consolidated import _changed_source_set, _valid_level2
from .overview import current_preview_records
from .query import query_merged_level2
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


def comparison_triplets(manga: Path, chapter: str) -> list[dict]:
    """Resolve original, effective Level I and effective Level II images."""
    if not chapter or chapter in {".", ".."} or Path(chapter).name != chapter:
        raise ValueError("Capítulo inválido.")
    level1 = _stage_manifest(manga, LEVEL1, chapter)
    if not level1:
        return []
    originals = _listing_merge_artifacts(manga / "IMG" / chapter)
    sources = level1.get("source_artifacts")
    if isinstance(sources, list) and sources and len(originals) != len(sources):
        raise OSError("Imagem original obrigatória ausente ou incompleta no MERGE.")
    clean_refs = level1.get("clean_artifacts")
    if level1.get("integrity_ok") is True and isinstance(clean_refs, list):
        folder = stage_chapter(manga, LEVEL1, chapter)
        if any(artifact_file(folder, ref, "clean") is None for ref in clean_refs):
            raise OSError("Imagem obrigatória do Nível I ausente.")
    if not _manifest_matches_merge(level1, manga, chapter):
        return []
    level1_folder = stage_chapter(manga, LEVEL1, chapter)
    raw_level2 = _stage_manifest(manga, LEVEL2, chapter)
    level2, level2_folder, _ = _valid_level2(
        manga, chapter, level1, _stage_manifest_sha256(manga, LEVEL1, chapter)
    )
    chapter_status = _level2_chapter_status(manga, chapter)
    candidates = set((level2 or {}).get("candidate_source_artifacts", []))
    if level2 is None and chapter_status.get("level2_status") == "pending":
        candidates = set(chapter_status.get("transparent_pages", []))
    changed = _changed_source_set(level2) if level2 else set()
    unchanged = set((level2 or {}).get("unchanged_source_artifacts", []))
    if level2 is None:
        _reject_missing_claimed_outputs(raw_level2, manga, chapter)
    pages = []
    for original in originals:
        source = original.name
        clean_name = original.stem + "_clean" + original.suffix
        level1_image = artifact_file(level1_folder, clean_name, "clean")
        if level1_image is None:
            raise OSError(f"Imagem obrigatória do Nível I ausente: {source}.")
        status = "pending" if source in candidates else "not_candidate"
        if level2 is None and chapter_status.get("level2_status") == "missing_level1":
            status = "unavailable"
        level2_image = level1_image
        if level2 and source in candidates:
            if source in changed:
                level2_image = artifact_file(level2_folder, clean_name, "clean")
                if level2_image is None:
                    raise OSError(f"Imagem obrigatória do Nível II ausente: {source}.")
                status = "changed"
            elif source in unchanged:
                status = "no_change"
        pages.append({"name": source, "original": original, "level1": level1_image,
                      "level2": level2_image, "level2_status": status,
                      "level2_chapter_status": chapter_status.get("level2_status", "pending")})
    return pages


def _level2_chapter_status(manga: Path, chapter: str) -> dict:
    result = query_merged_level2(manga)
    return next((row for row in result.get("chapters", [])
                 if row.get("chapter") == chapter), {})


def _reject_missing_claimed_outputs(manifest: dict, manga: Path, chapter: str) -> None:
    folder = stage_chapter(manga, LEVEL2, chapter)
    references = manifest.get("clean_artifacts", manifest.get("changed_artifacts", []))
    if isinstance(references, list):
        for reference in references:
            if isinstance(reference, str) and artifact_file(folder, reference, "clean") is None:
                raise OSError(f"Nível II declara imagem obrigatória ausente: {reference}.")
    changed = manifest.get("changed_source_artifacts", [])
    if not isinstance(changed, list):
        return
    for source in changed:
        if not isinstance(source, str) or Path(source).name != source:
            continue
        name = Path(source).stem + "_clean" + Path(source).suffix
        if artifact_file(folder, name, "clean") is None:
            raise OSError(f"Nível II declara alteração sem imagem obrigatória: {source}.")


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


def triplet_version(page: dict) -> str:
    signature = []
    for key in ("original", "level1", "level2"):
        path = page[key]
        info = path.stat()
        signature.append(f"{path.resolve()}:{info.st_size}:{info.st_mtime_ns}")
    signature.append(str(page.get("level2_status", "")))
    return hashlib.sha256("|".join(signature).encode()).hexdigest()
