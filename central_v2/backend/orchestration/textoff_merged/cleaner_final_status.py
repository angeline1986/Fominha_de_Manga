"""Current Glass and retouch origins in the official final chapter."""
from pathlib import Path

from .final_consolidated import final_manifest_path
from .final_consolidated_manifest import read_origin_pages

BRUSH_ORIGINS = {"PINCEL_DEGRADE": "degrade", "PINCEL_ARTISTICO": "artistic",
                 "PINCEL_SUAVE": "soft"}
ORIGINS = {*BRUSH_ORIGINS, "AUTO_CLEANER_TRANSPARENCIA", "LABORATORIO",
           "MANUAL_LAB_REPLACEMENT"}


def current_final_status(manga: Path, chapter: str) -> tuple[bool, set[str]]:
    """Report only verified pages that still occupy the Consolidado Final."""
    try:
        pages = read_origin_pages(final_manifest_path(manga, chapter), manga, chapter, ORIGINS)
    except (OSError, ValueError, TypeError, AttributeError):
        return False, set()
    glass = False
    retouch = set()
    for row in pages:
        origin = row["origin"]
        if origin == "AUTO_CLEANER_TRANSPARENCIA":
            glass = True
        elif origin in BRUSH_ORIGINS:
            retouch.add(BRUSH_ORIGINS[origin])
        elif (origin == "LABORATORIO" and row.get("visual_review") == "confirmed"
              and row.get("run_id") and row.get("laboratory_snapshot")):
            retouch.add("laboratory")
        elif (origin == "MANUAL_LAB_REPLACEMENT" and row.get("status") == "processed"
              and row.get("source_run_id") and row.get("source_artifact")):
            retouch.add("laboratory")
    return glass, retouch
