"""Build the final TextOff image set from the latest valid Merged level."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import tempfile
import uuid

from .artifact_paths import artifact_file, artifact_ref, prepare_artifact_dirs
from .artifact_migration import mirror_stage_chapter
from .manifests import _manifest_matches_merge, _stage_manifest, _stage_manifest_sha256
from .level2_vision import ALGORITHM as LEVEL2_ALGORITHM
from .stages import CONSOLIDATED, LEVEL1, LEVEL2, stage_chapter

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
    target = stage_chapter(manga, CONSOLIDATED, chapter, read_legacy=False)
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
            selections.append({"source": source_name, "selected_from": source_stage,
                               "artifact": artifact_ref("clean", destination_name),
                               "sha256": digest})
        manifest = {
            "schema_version": 1, "algorithm": ALGORITHM,
            "source_stage": CONSOLIDATED, "integrity_ok": True,
            "source_artifacts": source_names,
            "source_level1_manifest_sha256": level1_hash,
            "source_level2_manifest_sha256": level2_hash,
            "clean_artifacts": [item["artifact"] for item in selections],
            "outputs_total": len(source_names), "selections": selections,
        }
        (staged / "json/clean-manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        promote_stage(staged, target)
    mirror_stage_chapter(manga, "mapear_input_consolidado", chapter)
    return {"chapter": chapter, "outputs": len(source_names),
            "level2_outputs_used": sum(item["selected_from"] == LEVEL2 for item in selections)}


def consolidated_is_current(manga: Path, chapter: str) -> bool:
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
    if not _selected_pages_match(manifest, level1, level2):
        return False
    selections = manifest.get("selections")
    outputs = manifest.get("clean_artifacts")
    if not isinstance(outputs, list) or len(outputs) != len(level1.get("source_artifacts", [])):
        return False
    if not isinstance(selections, list) or len(selections) != len(outputs):
        return False
    return all(_selection_is_current(folder, item, level1, manga, chapter) for item in selections)


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
                                            candidate_names, changed_sources, unchanged_sources, names))
    return (manifest if valid else None, folder if valid else None, digest if valid else None)


def _selected_pages_match(manifest, level1, level2):
    selected = manifest.get("selections")
    if not isinstance(selected, list):
        return False
    level2_sources = _changed_source_set(level2) if level2 else set()
    sources = level1.get("source_artifacts", [])
    return (len(selected) == len(sources)
            and all(isinstance(item, dict) for item in selected)
            and [item["source"] for item in selected] == sources
            and all(item.get("selected_from") == (LEVEL2 if item.get("source") in level2_sources else LEVEL1)
                    for item in selected))


def _selection_is_current(folder, item, level1, manga, chapter):
    if not isinstance(item, dict):
        return False
    source = item.get("source")
    if not isinstance(source, str) or Path(source).name != source:
        return False
    name = Path(source).stem + "_clean" + Path(source).suffix
    if item.get("artifact") != artifact_ref("clean", name):
        return False
    source_stage = item.get("selected_from")
    if source_stage == LEVEL2:
        source_folder = stage_chapter(manga, LEVEL2, chapter)
        path = artifact_file(source_folder, name, "clean")
    elif source_stage == LEVEL1:
        source_folder = stage_chapter(manga, LEVEL1, chapter)
        path = artifact_file(source_folder, name, "clean")
    else:
        return False
    if path is None or _sha256(path) != item.get("sha256"):
        return False
    if source_stage == LEVEL2:
        consolidated_copy = artifact_file(folder, item["artifact"], "clean")
        return consolidated_copy is not None and _sha256(consolidated_copy) == item.get("sha256")
    if artifact_file(folder, item["artifact"], "clean") is not None:
        return False
    return source_stage == LEVEL1


def _artifact_map(manifest, folder):
    result = {}
    for reference in manifest.get("clean_artifacts", []):
        path = artifact_file(folder, reference, "clean")
        if path is not None:
            result[Path(reference).name] = path
    return result


def _select_artifacts(source_names, level1, level1_dir, level2, level2_dir):
    level1_files = _artifact_map(level1, level1_dir)
    level2_files = _artifact_map(level2, level2_dir) if level2 else {}
    level2_sources = _changed_source_set(level2) if level2 else set()
    selected = []
    for source in source_names:
        name = Path(source).stem + "_clean" + Path(source).suffix
        use_level2 = source in level2_sources
        path = level2_files.get(name) if use_level2 else level1_files.get(name)
        if path is None:
            raise ValueError(f"Imagem limpa ausente para consolidar {source}.")
        selected.append((path, LEVEL2 if use_level2 else LEVEL1))
    return selected


def _valid_level2_page_results(folder, level1_folder, manifest, page_results,
                               candidates, changed_sources, unchanged_sources, clean_names):
    rows = {item.get("source"): item for item in page_results}
    clean_by_source = {
        Path(source).stem + Path(source).suffix:
        artifact_ref("clean", Path(source).stem + "_clean" + Path(source).suffix)
        for source in candidates
    }
    clean_set = set(clean_names)
    masks = manifest.get("mask_artifacts")
    if not isinstance(masks, list) or len(masks) != len(candidates) or len(masks) != len(set(masks)):
        return False
    row_masks = []
    for source in candidates:
        row = rows[source]
        expected_clean = clean_by_source[Path(source).name]
        if row.get("level1_clean") != expected_clean:
            return False
        if artifact_file(level1_folder, row.get("level1_clean"), "clean") is None:
            return False
        mask = row.get("mask")
        if artifact_file(folder, mask, "mask") is None:
            return False
        row_masks.append(mask)
        pixels = row.get("changed_pixels")
        if not isinstance(pixels, int) or isinstance(pixels, bool) or pixels < 0:
            return False
        mask_pixels = row.get("mask_pixels")
        if not isinstance(mask_pixels, int) or isinstance(mask_pixels, bool) or mask_pixels < 0:
            return False
        clean = row.get("clean")
        if source in changed_sources:
            if clean != expected_clean or clean not in clean_set or pixels <= 0:
                return False
        elif source in unchanged_sources:
            if clean is not None or pixels != 0:
                return False
        else:
            return False
    if set(row_masks) != set(masks):
        return False
    report_ref = manifest.get("report")
    report_path = artifact_file(folder, report_ref, "json")
    if report_path is None:
        return False
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return False
    report_pages = report.get("pages")
    if (report.get("integrity_ok") is not True
            or report.get("pages_analyzed") != len(candidates)
            or not isinstance(report_pages, list)
            or len(report_pages) != len(candidates)):
        return False
    report_by_source = {item.get("source"): item for item in report_pages if isinstance(item, dict)}
    if len(report_by_source) != len(candidates) or set(report_by_source) != set(candidates):
        return False
    for source in candidates:
        row, report_row = rows[source], report_by_source[source]
        if any(report_row.get(key) != row.get(key)
               for key in ("clean", "level1_clean", "mask", "changed_pixels", "mask_pixels")):
            return False
        if report_row.get("changed_outside_mask") != 0:
            return False
    return True


def _source_from_clean(reference):
    name = Path(str(reference)).name
    path = Path(name)
    suffix = path.suffix
    stem = path.stem
    return stem[:-6] + suffix if stem.endswith("_clean") else name


def _changed_source_set(manifest):
    changed = manifest.get("changed_source_artifacts")
    if isinstance(changed, list):
        return set(changed)
    return set(manifest.get("candidate_source_artifacts", []))


def _valid_legacy_level2(folder, level1_folder, level1, level1_hash, manifest):
    candidates = manifest.get("candidate_source_artifacts")
    outputs = manifest.get("clean_artifacts")
    changed = manifest.get("changed_artifacts", outputs)
    if (manifest.get("integrity_ok") is not True
            or manifest.get("algorithm") != LEVEL2_ALGORITHM
            or manifest.get("source_stage") not in {LEVEL1, "MERGED_NIVEL_I"}
            or manifest.get("source_level1_manifest_sha256") != level1_hash
            or manifest.get("source_artifacts") != level1.get("source_artifacts")
            or not isinstance(candidates, list) or len(candidates) != len(set(candidates))
            or int(manifest.get("pages_total") or 0) != len(candidates)
            or not set(candidates).issubset(set(level1.get("source_artifacts", [])))
            or not isinstance(outputs, list) or len(outputs) != len(candidates)
            or len(outputs) != len(set(outputs)) or not isinstance(changed, list)
            or set(changed) != set(outputs) or int(manifest.get("outputs_total") or 0) != len(outputs)):
        return False
    expected_names = {Path(source).stem + "_clean" + Path(source).suffix for source in candidates}
    if ({Path(name).name for name in outputs} != expected_names
            or any(artifact_file(folder, name, "clean") is None for name in outputs)):
        return False
    expected_level1 = [item for item in level1.get("clean_artifacts", [])
                       if _source_from_clean(item) in candidates]
    if manifest.get("source_level1_artifacts") not in (None, expected_level1):
        return False
    report_path = artifact_file(folder, manifest.get("report"), "json")
    if report_path is None:
        return False
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return False
    pages = report.get("pages")
    if (report.get("integrity_ok") is not True or report.get("pages_analyzed") != len(candidates)
            or not isinstance(pages, list) or len(pages) != len(candidates)):
        return False
    by_source = {item.get("source"): item for item in pages if isinstance(item, dict)}
    if len(by_source) != len(candidates) or set(by_source) != set(candidates):
        return False
    masks = manifest.get("mask_artifacts")
    if not isinstance(masks, list) or len(masks) != len(candidates) or len(masks) != len(set(masks)):
        return False
    for source in candidates:
        row = by_source[source]
        clean = artifact_ref("clean", Path(source).stem + "_clean" + Path(source).suffix)
        level1_clean = clean
        if (row.get("clean") != clean or row.get("changed_outside_mask") != 0
                or artifact_file(folder, clean, "clean") is None
                or artifact_file(level1_folder, level1_clean, "clean") is None
                or artifact_file(folder, row.get("mask"), "mask") is None):
            return False
    return set(masks) == {row.get("mask") for row in pages}


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
