"""Read-only stage indicators for the cleaner worklist."""
from pathlib import Path

from .query import query_merged_level2
from .level3_styled import query_level3
from central_v2.backend.orchestration.textoff_special.artifacts import (
    contained_file, read_json, sha256,
)
from central_v2.backend.orchestration.textoff_special.catalog import STAGING_ROOT
from central_v2.backend.orchestration.textoff_special.inputs import resolve_input

TREATMENTS = {"degrade": "degrade", "estilizado": "artistic", "gradiente_suave": "soft"}


def query_cleaner_overview(manga: Path) -> dict:
    result = query_merged_level2(manga)
    mapped = {row["chapter"]: row["cleaned"] for row in query_level3(manga)["chapters"]}
    previews = current_previews(manga)
    for row in result["chapters"]:
        flags = previews.get(row["chapter"], set()) if row["cleaned"] else set()
        row["stages"] = {
            "ac1": row["cleaned"],
            "ac2": row["level2_status"] in {"processed", "no_change"},
            "ac3": "ac3" in flags,
            "ac4": "ac4" in flags,
            "map": mapped.get(row["chapter"], False),
        }
        row["retouch"] = {key: key in flags for key in TREATMENTS.values()}
        row["selectable"] = row["merge_valid"]
    return result


def current_previews(manga: Path, staging: Path = STAGING_ROOT) -> dict:
    """Count successful, current previews; never infer official promotion."""
    results = {}
    for key, manifest in current_preview_records(manga, staging):
        results.setdefault(manifest["source"]["chapter"], set()).add(key)
    return results


def current_preview_records(manga: Path, staging: Path = STAGING_ROOT):
    """Yield validated previews with their original outcome metadata."""
    for path in staging.glob("*/manifest.json"):
        try:
            manifest = read_json(path)
            source = manifest.get("source", {})
            if (manifest.get("execution_status") != "succeeded"
                    or source.get("manga") != str(manga.resolve())
                    or source.get("level") != "MERGED_NIVEL_I"):
                continue
            key = TREATMENTS.get(manifest.get("treatment"))
            if manifest.get("merged_level") == "IV" and manifest.get("treatment") == "transparente":
                key = "ac3"
            if manifest.get("merged_level") == "V" and manifest.get("treatment") == "transparente_legacy":
                key = "ac4"
            if key is None:
                continue
            current = resolve_input(manga, source["level"], source["chapter"],
                                    source["filename"], source["sha256"])
            if current["predecessors"] != source.get("predecessors"):
                continue
            output = contained_file(path.parent, manifest["result_file"])
            if sha256(output) != manifest["validation"]["result_sha256"]:
                continue
            yield key, manifest
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            continue


def query_mapping_worklist(manga: Path) -> dict:
    result = query_level3(manga)
    previews = current_previews(manga)
    for row in result["chapters"]:
        flags = previews.get(row["chapter"], set()) if row["merge_valid"] else set()
        row["retouch"] = {key: key in flags for key in TREATMENTS.values()}
    return result
