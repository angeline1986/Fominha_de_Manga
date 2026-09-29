"""Read and validate MERGE and TextOff stage manifests."""
import hashlib
import json
from pathlib import Path

from processamento.unificacao_imagens import image_stitcher as v3

def _clean_manifest(manga: Path, chapter: str) -> dict:
    path = manga / "FLUXO_SECUNDARIO" / "04_TEXTO_OFF" / "MERGED" / chapter / "clean-manifest.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def _listing_merge_artifacts(chapter: Path) -> list[Path]:
    """Read MERGE metadata and check file presence without decoding image pixels."""
    manifest_path = v3.merge_manifest_path(chapter)
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        outputs = manifest.get("outputs")
        expected_count = int(manifest.get("merged_images") or 0)
        source_height = int(manifest.get("source_total_height") or 0)
    except (OSError, ValueError, TypeError, AttributeError):
        return []
    if not isinstance(outputs, list) or not outputs or len(outputs) != expected_count:
        return []

    output_dir = manifest_path.parent
    artifacts = []
    position = 0
    for item in outputs:
        if not isinstance(item, dict):
            return []
        filename = str(item.get("file") or "")
        try:
            start, end = int(item["global_start"]), int(item["global_end"])
            height = int(item.get("height", end - start))
        except (KeyError, TypeError, ValueError):
            return []
        if (not filename or Path(filename).name != filename or start != position
                or end <= start or height != end - start):
            return []
        artifact = output_dir / filename
        if not artifact.is_file():
            return []
        artifacts.append(artifact)
        position = end
    if position != source_height:
        return []
    return artifacts


def _stage_manifest(manga: Path, stage: str, chapter: str) -> dict:
    path = manga / "FLUXO_SECUNDARIO" / "04_TEXTO_OFF" / stage / chapter / "clean-manifest.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def _stage_manifest_sha256(manga: Path, stage: str, chapter: str) -> str | None:
    path = manga / "FLUXO_SECUNDARIO" / "04_TEXTO_OFF" / stage / chapter / "clean-manifest.json"
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _manifest_matches_merge(manifest: dict, manga: Path, chapter: str) -> bool:
    images = _listing_merge_artifacts(manga / "IMG" / chapter)
    outputs = manifest.get("clean_artifacts")
    output_dir = manga / "FLUXO_SECUNDARIO" / "04_TEXTO_OFF" / "MERGED_NIVEL_I" / chapter
    return bool(images) and isinstance(outputs, list) and len(outputs) == len(images) and all(
        isinstance(name, str) and Path(name).name == name and (output_dir / name).is_file()
        for name in outputs
    ) and (
        manifest.get("source_stage") == "MERGE"
        and manifest.get("integrity_ok") is True
        and manifest.get("source_artifacts") == [path.name for path in images]
        and manifest.get("outputs_total") == len(images)
    )


def _transparent_masks_ready(manga: Path, chapter: str, manifest: dict) -> bool:
    level1 = manifest.get("level1") if isinstance(manifest.get("level1"), dict) else {}
    if level1.get("algorithm") != "textoff_level1_balloon_transparency_gate_v4":
        return False
    names = level1.get("transparent_mask_artifacts")
    expected = int(manifest.get("pages_total") or 0)
    folder = manga / "FLUXO_SECUNDARIO" / "04_TEXTO_OFF" / "MERGED_NIVEL_I" / chapter
    artifacts_ready = isinstance(names, list) and len(names) == expected and all(
        isinstance(name, str) and Path(name).name == name and (folder / name).is_file()
        for name in names
    )
    if not artifacts_ready:
        return False
    report_name = level1.get("report")
    if not isinstance(report_name, str) or Path(report_name).name != report_name:
        return False
    try:
        report = json.loads((folder / report_name).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return False
    balloons = [balloon for page in report.get("pages", []) if isinstance(page, dict)
                for balloon in page.get("transparent_balloons", []) if isinstance(balloon, dict)]
    labels = [balloon.get("mask_label") for balloon in balloons]
    return (len(balloons) == int(level1.get("transparent_balloons_total") or 0)
            and all(type(label) is int and label > 0 for label in labels)
            and len(labels) == len(set(labels)))


def _deferred_text_masks_ready(manga: Path, chapter: str, manifest: dict) -> bool:
    level1 = manifest.get("level1") if isinstance(manifest.get("level1"), dict) else {}
    if not int(level1.get("transparent_components_deferred") or 0):
        return True
    folder = manga / "FLUXO_SECUNDARIO" / "04_TEXTO_OFF" / "MERGED_NIVEL_I" / chapter
    report_name = level1.get("report")
    if not isinstance(report_name, str) or Path(report_name).name != report_name:
        return False
    try:
        report = json.loads((folder / report_name).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return False
    deferred_pages = [
        page for page in report.get("pages", [])
        if isinstance(page, dict) and int(page.get("transparent_components_deferred") or 0) > 0
    ]
    return all(
        isinstance(page.get("deferred_text_mask_artifact"), str)
        and Path(page["deferred_text_mask_artifact"]).name == page["deferred_text_mask_artifact"]
        and (folder / page["deferred_text_mask_artifact"]).is_file()
        for page in deferred_pages
    )
