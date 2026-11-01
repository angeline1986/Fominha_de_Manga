"""Keep pre-Glass Mapear results tied to their original Level I images."""
import hashlib
import json
from pathlib import Path

from .artifact_paths import artifact_file
from .consolidated_artifacts import consolidated_image
from .stages import CONSOLIDATED, LEVEL1, LEVEL2, LEVEL3, stage_chapter


def _digest(path: Path) -> str | None:
    try:
        result = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                result.update(block)
        return result.hexdigest()
    except OSError:
        return None


def _document(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def _level1_image(manga: Path, chapter: str, name: str) -> Path | None:
    if not isinstance(name, str) or Path(name).name != name or name in {"", ".", ".."}:
        return None
    source = artifact_file(stage_chapter(manga, LEVEL1, chapter), name, "clean")
    if (source is None or source.is_symlink()
            or not source.resolve().is_relative_to(Path(manga).resolve())):
        return None
    return source


def pre_glass_mapear_current(manga: Path, chapter: str, manifest: dict) -> bool:
    """Accept the recorded pre-Glass input only when Level I is unchanged."""
    level1_manifest = stage_chapter(manga, LEVEL1, chapter) / "json/clean-manifest.json"
    intermediate = _document(stage_chapter(manga, CONSOLIDATED, chapter)
                             / "json/clean-manifest.json")
    names = manifest.get("source_artifacts")
    hashes = manifest.get("source_artifact_sha256")
    selections = intermediate.get("selections")
    artifacts = intermediate.get("clean_artifacts")
    level1_hash = manifest.get("source_level1_manifest_sha256")
    if (manifest.get("source_level2_manifest_sha256") is not None
            or not isinstance(manifest.get("source_consolidated_manifest_sha256"), str)
            or not isinstance(level1_hash, str) or level1_hash != _digest(level1_manifest)
            or intermediate.get("source_level1_manifest_sha256") != level1_hash
            or not isinstance(intermediate.get("source_level2_manifest_sha256"), str)
            or intermediate.get("source_combo_manifest_sha256") is not None
            or not isinstance(names, list) or not names
            or any(not isinstance(name, str) for name in names)
            or len(names) != len(set(names))
            or not isinstance(hashes, list) or len(hashes) != len(names)
            or not isinstance(selections, list) or len(selections) != len(names)
            or any(not isinstance(item, dict) for item in selections)
            or not isinstance(artifacts, list) or len(artifacts) != len(names)
            or any(not isinstance(item, str) for item in artifacts)
            or [item.get("artifact") for item in selections] != artifacts
            or [Path(item).name for item in artifacts] != names
            or any(item.get("selected_from") not in {LEVEL1, LEVEL2}
                   for item in selections)):
        return False
    for name, expected in zip(names, hashes):
        source = _level1_image(manga, chapter, name)
        if not isinstance(expected, str) or source is None or _digest(source) != expected:
            return False
    return True


def mapear_input_image(manga: Path, chapter: str, filename: str) -> Path | None:
    """Serve the image Mapear analyzed, even after Glass changes Consolidado."""
    manifest = _document(stage_chapter(manga, LEVEL3, chapter) / "json/clean-manifest.json")
    names = manifest.get("source_artifacts")
    hashes = manifest.get("source_artifact_sha256")
    if (not isinstance(names, list) or not isinstance(hashes, list)
            or names.count(filename) != 1 or len(names) != len(hashes)):
        return None
    expected = hashes[names.index(filename)]
    level1_hash = manifest.get("source_level1_manifest_sha256")
    if (manifest.get("source_level2_manifest_sha256") is None
            and isinstance(level1_hash, str) and level1_hash == _digest(
                stage_chapter(manga, LEVEL1, chapter) / "json/clean-manifest.json")):
        level1 = _level1_image(manga, chapter, filename)
        if level1 is not None and _digest(level1) == expected:
            return level1
    current = consolidated_image(manga, chapter, filename)
    if current is not None and _digest(current) == expected:
        return current
    return None
