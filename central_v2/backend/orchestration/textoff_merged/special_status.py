"""Project experimental transparency outcomes without promoting previews."""
from pathlib import Path

from .special_levels import query_special_level
from .overview import current_preview_records


def query_special_worklist(manga: Path, level: str) -> dict:
    result = query_special_level(manga, level)
    key = {"IV": "ac3", "V": "ac4"}[level]
    latest = {}
    for stage, manifest in current_preview_records(manga):
        if stage != key:
            continue
        source = manifest["source"]
        identity = (source["chapter"], source["filename"])
        if manifest.get("finished_at", "") >= latest.get(identity, {}).get("finished_at", ""):
            latest[identity] = manifest
    for row in result["chapters"]:
        expected = {Path(name).stem + "_clean" + Path(name).suffix
                    for name in row.get("transparent_pages", [])}
        completed = {filename: manifest for (chapter, filename), manifest in latest.items()
                     if chapter == row["chapter"] and filename in expected}
        if not row["level1_ready"]:
            status = "missing_level1"
        elif not expected:
            status = "no_candidates"
        elif not expected.issubset(completed):
            status = "pending"
        elif any(item["validation"].get("changed_pixels", 0) > 0 for item in completed.values()):
            status = "processed"
        else:
            status = "no_change"
        row["cleaner_status"] = status
    return result
