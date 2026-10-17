"""Select and validate page sources for the logical consolidated stage."""
from pathlib import Path

from central_v2.backend.orchestration.textoff_special.artifacts import sha256
from .artifact_paths import artifact_file, artifact_ref
from .level2_legacy_validation import _changed_source_set
from .stages import COMBO_TURBO, LEVEL1, LEVEL2, stage_chapter


def _selected_pages_match(manifest, level1, level2, manga, chapter):
    selected = manifest.get("selections")
    if not isinstance(selected, list):
        return False
    level2_sources = _changed_source_set(level2) if level2 else set()
    sources = level1.get("source_artifacts", [])
    if (len(selected) != len(sources) or not all(isinstance(item, dict) for item in selected)
            or [item.get("source") for item in selected] != sources):
        return False
    from central_v2.backend.orchestration.combo_turbo.publication_validation import validate_published_page
    for item in selected:
        combo = validate_published_page(manga, chapter, item["source"], item.get("sha256"))
        expected = COMBO_TURBO if combo else (LEVEL2 if item["source"] in level2_sources else LEVEL1)
        if item.get("selected_from") != expected:
            return False
        if expected == COMBO_TURBO and item.get("source_artifact") != combo.get("artifact"):
            return False
    return True


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
    if source_stage == COMBO_TURBO:
        from central_v2.backend.orchestration.combo_turbo.publication_validation import validate_published_page
        combo = validate_published_page(manga, chapter, source, item.get("sha256"))
        return (bool(combo) and item.get("source_artifact") == combo.get("artifact")
                and artifact_file(folder, item["artifact"], "clean") is None)
    if source_stage == LEVEL2:
        source_folder = stage_chapter(manga, LEVEL2, chapter)
        path = artifact_file(source_folder, name, "clean")
    elif source_stage == LEVEL1:
        source_folder = stage_chapter(manga, LEVEL1, chapter)
        path = artifact_file(source_folder, name, "clean")
    else:
        return False
    if path is None or sha256(path) != item.get("sha256"):
        return False
    if source_stage == LEVEL2:
        consolidated_copy = artifact_file(folder, item["artifact"], "clean")
        return consolidated_copy is not None and sha256(consolidated_copy) == item.get("sha256")
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


def _combo_selections(manga, chapter, source_names):
    from central_v2.backend.orchestration.combo_turbo.publication_manifest import MANIFEST, read_manifest
    from central_v2.backend.orchestration.combo_turbo.publication_validation import validate_published_page
    folder = stage_chapter(manga, COMBO_TURBO, chapter, read_legacy=False)
    pathname = folder / "json" / MANIFEST
    if not pathname.exists():
        if folder.exists() and any(folder.iterdir()):
            raise ValueError("Estágio Combo parcial; consolidação bloqueada.")
        return None, {}
    manifest = read_manifest(manga, chapter)
    digest = sha256(pathname)
    rows = {}
    for source in source_names:
        row = manifest["pages"].get(source)
        if not isinstance(row, dict) or row.get("status") != "COMPOSED":
            continue
        checked = validate_published_page(manga, chapter, source, row.get("sha256"))
        if checked is None:
            raise ValueError(f"Resultado Combo inválido ou obsoleto: {source}.")
        rows[source] = (checked["path"], row["artifact"])
    return digest, rows
