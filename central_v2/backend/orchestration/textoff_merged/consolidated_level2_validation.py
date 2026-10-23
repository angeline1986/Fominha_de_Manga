"""Validate current and legacy Level II chapter manifests."""
from pathlib import Path

from .artifact_paths import artifact_file
from .level2_legacy_validation import _source_from_clean, _valid_legacy_level2
from .level2_result_validation import _valid_level2_page_results
from .level2_vision import ALGORITHM as LEVEL2_ALGORITHM
from .manifests import _stage_manifest, _stage_manifest_sha256
from .stages import LEVEL1, LEVEL2, stage_chapter


def _valid_level2(manga, chapter, level1, level1_hash):
    try:
        return _valid_level2_unchecked(manga, chapter, level1, level1_hash)
    except (OSError, TypeError, ValueError, KeyError, OverflowError):
        return None, None, None


def _valid_level2_unchecked(manga, chapter, level1, level1_hash):
    folder = stage_chapter(manga, LEVEL2, chapter)
    level1_folder = stage_chapter(manga, LEVEL1, chapter)
    manifest = _stage_manifest(manga, LEVEL2, chapter)
    digest = _stage_manifest_sha256(manga, LEVEL2, chapter)
    accepted_sources = {LEVEL1, "MERGED_NIVEL_I"}
    names = manifest.get("clean_artifacts")
    changed_names = manifest.get("changed_artifacts", names)
    candidate_names = manifest.get("candidate_source_artifacts")
    expected = {Path(source).stem + "_clean" + Path(source).suffix
                for source in candidate_names} if isinstance(candidate_names, list) else set()
    analyzed_sources = manifest.get("analyzed_source_artifacts")
    changed_sources = manifest.get("changed_source_artifacts")
    unchanged_sources = manifest.get("unchanged_source_artifacts")
    page_results = manifest.get("page_results")
    if not isinstance(manifest.get("analyzed_source_artifacts"), list):
        legacy_valid = _valid_legacy_level2(folder, level1_folder, level1, level1_hash, manifest)
        return (manifest if legacy_valid else None, folder if legacy_valid else None,
                digest if legacy_valid else None)
    expected_level1 = [item for item in level1.get("clean_artifacts", [])
                       if _source_from_clean(item) in candidate_names] if isinstance(candidate_names, list) else []
    valid = (manifest.get("integrity_ok") is True
             and manifest.get("algorithm") == LEVEL2_ALGORITHM
             and manifest.get("source_stage") in accepted_sources
             and manifest.get("source_level1_manifest_sha256") == level1_hash
             and manifest.get("source_artifacts") == level1.get("source_artifacts")
             and isinstance(names, list) and isinstance(candidate_names, list)
             and len(candidate_names) == len(set(candidate_names))
             and int(manifest.get("pages_total") or 0) == len(candidate_names)
             and int(manifest.get("analyzed_pages_total") or 0) == len(candidate_names)
             and set(candidate_names).issubset(set(level1.get("source_artifacts", [])))
             and manifest.get("source_level1_artifacts") == expected_level1
             and isinstance(analyzed_sources, list) and len(analyzed_sources) == len(set(analyzed_sources))
             and set(analyzed_sources) == set(candidate_names)
             and isinstance(changed_sources, list) and len(changed_sources) == len(set(changed_sources))
             and isinstance(unchanged_sources, list) and len(unchanged_sources) == len(set(unchanged_sources))
             and set(changed_sources).isdisjoint(unchanged_sources)
             and set(changed_sources) | set(unchanged_sources) == set(candidate_names)
             and int(manifest.get("changed_pages_total") or 0) == len(changed_sources)
             and manifest.get("outcome") == ("visual_changes" if changed_sources else "no_visual_change")
             and isinstance(page_results, list) and len(page_results) == len(candidate_names)
             and all(isinstance(item, dict) for item in page_results)
             and len({item.get("source") for item in page_results}) == len(candidate_names)
             and {item.get("source") for item in page_results} == set(candidate_names)
             and isinstance(names, list) and len(names) == len(set(names))
             and int(manifest.get("outputs_total") or 0) == len(names)
             and isinstance(changed_names, list) and len(changed_names) == len(set(changed_names))
             and set(changed_names) == set(names)
             and {Path(name).name for name in names}.issubset(expected)
             and all(artifact_file(folder, name, "clean") is not None for name in names)
             and _valid_level2_page_results(folder, level1_folder, manifest, page_results,
                                            candidate_names, changed_sources, unchanged_sources,
                                            names, manga, chapter))
    return (manifest if valid else None, folder if valid else None, digest if valid else None)
