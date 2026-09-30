"""Resolve manifest-backed images in the virtual consolidated TextOff stage."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .artifact_paths import artifact_file, artifact_ref
from .stages import LEVEL1, LEVEL2, stage_chapter


def consolidated_image(manga: Path, chapter: str, filename: str) -> Path | None:
    folder = stage_chapter(manga, "TO_MERGED_CONSOLIDADO", chapter, read_legacy=False)
    try:
        manifest = json.loads((folder / "json/clean-manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    selection = next((item for item in manifest.get("selections", [])
                      if item.get("artifact") == artifact_ref("clean", filename)), None)
    if not isinstance(selection, dict):
        return None
    stage = LEVEL2 if selection.get("selected_from") == LEVEL2 else LEVEL1
    source = stage_chapter(manga, stage, chapter)
    path = artifact_file(source, selection.get("artifact"), "clean")
    return path if path is not None and _sha256(path) == selection.get("sha256") else None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
