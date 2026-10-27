"""Read saved Check decisions and their verified review images."""
from pathlib import Path

from central_v2.backend.orchestration.textoff_merged.auto_cleaner_check_images import check_image
from central_v2.backend.orchestration.textoff_merged.auto_cleaner_check_manifest import (
    CHECK_STAGE, _read_check_manifest, manifest_path,
)
from central_v2.backend.orchestration.textoff_merged.stages import stage_root
from central_v2.backend.state.manga_state import IMAGE_EXTENSIONS
from central_v2.backend.state.sorting import natural_sort_key


def _saved(manga, provider, chapter):
    path = manifest_path(manga, chapter)
    if not path.is_file():
        return None
    document = {"provider": provider, "obra": manga.name, "capitulo": chapter}
    return _read_check_manifest(path, document)


def _other_names(manifest):
    return {row["page"] for row in manifest["approved_occurrences"]
            if row.get("tipo") == "outro" and isinstance(row.get("page"), str)
            and row["page"] not in {".", ".."}
            and Path(row["page"]).name == row["page"]
            and "\\" not in row["page"]
            and Path(row["page"]).suffix.lower() in IMAGE_EXTENSIONS}


def other_pages(manga, provider, chapter):
    manifest = _saved(manga, provider, chapter)
    return _other_names(manifest) if manifest is not None else set()


def check_chapter_names(manga):
    work = Path(manga).resolve()
    root = stage_root(work, CHECK_STAGE, read_legacy=False)
    if not root.is_dir() or not root.resolve().is_relative_to(work):
        return []
    return sorted((folder.name for folder in root.iterdir()
                   if folder.is_dir() and not folder.is_symlink()
                   and (folder / "auto-cleaner-check-manifest.json").is_file()),
                  key=natural_sort_key)


def check_pages(manga, provider, chapter):
    manifest = _saved(manga, provider, chapter)
    if manifest is None:
        return {}
    names = _other_names(manifest)
    snapshots = manifest.get("image_snapshot")
    if snapshots is None:
        from central_v2.backend.orchestration.textoff_merged.comparison import comparison_pairs
        sources = {row["name"]: row["after"] for row in
                   comparison_pairs(manga, chapter, "1", check=True)}
    else:
        sources = {name: check_image(manga, chapter, name, None) for name in names}
    work = Path(manga).resolve()
    return {name: path.resolve() for name in names
            if (path := sources.get(name)) is not None
            and path.resolve().is_relative_to(work) and path.is_file()}
