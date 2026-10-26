"""Read-only stage indicators for the cleaner worklist."""
from pathlib import Path

from .query import query_merged_level2
from .level3_styled import query_level3
from .artifact_migration import registry_snapshot
from .manifests import manifest_snapshot
from .stages import stage_path_snapshot, stage_chapter
from .auto_cleaner_check_manifest import manifest_path, SCHEMA as CHECK_SCHEMA
from .cleaner_final_status import current_final_status
from central_v2.backend.orchestration.bubble_sommelier.query import _sommelier_state
import json
from central_v2.backend.orchestration.textoff_special.artifacts import (
    contained_file, read_json, sha256,
)
from central_v2.backend.orchestration.textoff_special.catalog import STAGING_ROOT
from central_v2.backend.orchestration.textoff_special.run_paths import roots
from central_v2.backend.orchestration.textoff_special.inputs import resolve_input

TREATMENTS = {"degrade": "degrade", "estilizado": "artistic", "gradiente_suave": "soft"}


def query_cleaner_overview(manga: Path) -> dict:
    with registry_snapshot(), manifest_snapshot(), stage_path_snapshot():
        return _query_cleaner_overview(manga)


def _query_cleaner_overview(manga: Path) -> dict:
    result = query_merged_level2(manga, check_resets=True)
    merge_rows = {row["chapter"]: row for row in result["chapters"]}
    mapped = {row["chapter"]: row["cleaned"]
              for row in query_level3(manga, merge_rows)["chapters"]}
    previews = current_previews(manga)
    for row in result["chapters"]:
        flags = previews.get(row["chapter"], set()) if row["cleaned"] else set()
        final_glass, final_retouch = current_final_status(manga, row["chapter"])
        row["stages"] = {
            "ac1": row["cleaned"],
            "ac2": row["level2_status"] in {"processed", "no_change"},
            "ac3": "ac3" in flags,
            "ac4": "ac4" in flags,
            "map": mapped.get(row["chapter"], False),
        }
        chapter = row["chapter"]
        bubble = stage_chapter(manga, "BUBBLE_SOMMELIER", chapter) / "report.json"
        check = manifest_path(manga, chapter)
        solid = stage_chapter(manga, "05_AUTO_CLEANER_SOLIDOS", chapter,
                              read_legacy=False) / "solid-white-manifest.json"
        row["stages"].update({
            "bubble": bool(_sommelier_state(bubble)),
            "check": _verified_manifest(check, CHECK_SCHEMA, chapter),
            "solids": _verified_manifest(solid, "textoff_solid_stage_v1", chapter),
            "glass": row["stages"]["ac2"] or "ac3" in flags or "ac4" in flags or final_glass,
        })
        row["retouch"] = {key: key in flags or key in final_retouch
                          for key in (*TREATMENTS.values(), "laboratory")}
        row["selectable"] = row["merge_valid"]
    return result


def _verified_manifest(path: Path, schema: str, chapter: str) -> bool:
    try:
        content = json.loads(path.read_text(encoding="utf-8"))
        return (isinstance(content, dict) and content.get("schema") == schema
                and content.get("chapter") == chapter)
    except (OSError, ValueError, TypeError):
        return False


def current_previews(manga: Path, staging: Path = STAGING_ROOT) -> dict:
    """Count successful, current previews; never infer official promotion."""
    results = {}
    for key, manifest in current_preview_records(manga, staging):
        results.setdefault(manifest["source"]["chapter"], set()).add(key)
    return results


def current_preview_records(manga: Path, staging: Path = STAGING_ROOT):
    """Yield validated previews with their original outcome metadata."""
    for root in roots(manga, "textoff_especiais_v2", legacy=staging):
        for path in root.glob("*/manifest.json"):
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
