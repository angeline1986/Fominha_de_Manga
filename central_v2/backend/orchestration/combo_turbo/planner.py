"""Deterministic page-level planning for the isolated Combo Turbo runner."""
import json
from pathlib import Path

from central_v2.backend.orchestration.textoff_merged.solid_stage import rows_for
from central_v2.backend.orchestration.textoff_merged.stages import LEVEL1, stage_chapter

from .models import valid_chapter_id, valid_page_id
from .validation import validate_chapter


def plan_chapter(manga, provider, chapter, *, repair_isolated_outputs=False):
    """Plan each candidate page without executing either cleaner."""
    if not valid_chapter_id(chapter):
        return {"chapter": chapter, "status": "BLOCKED", "reasons": ["INVALID_CHAPTER"], "pages": []}
    root = Path(manga).resolve()
    try:
        review = validate_chapter(root, provider, chapter)
        solids_rows, _ = rows_for(root, {"provider": provider, "obra": root.name,
                                         "capitulo": chapter}, chapter)
        solid_pages = {row.get("page") for row in solids_rows if valid_page_id(row.get("page"))}
        glass_pages = _glass_candidates(root, chapter)
    except (OSError, ValueError, TypeError, KeyError, RuntimeError) as exc:
        return {"chapter": chapter, "status": "BLOCKED", "reasons": ["AUTHORITY_UNAVAILABLE"],
                "error": str(exc), "pages": []}
    records = {stage: {item["page"]: item for item in review["results"][stage]}
               for stage in ("SOLIDOS", "GLASS")}
    pages = []
    for page in review["pages"]:
        eligible = {"SOLIDOS": page in solid_pages, "GLASS": page in glass_pages}
        stages = {}
        for stage in eligible:
            item = records[stage][page]
            stages[stage] = _action(item, eligible[stage], repair_isolated_outputs)
        pages.append({"page": page, "eligible": eligible, "stages": stages,
                      "action": _page_action(stages)})
    blocked = any(p["action"] == "BLOCKED" for p in pages)
    no_work = not pages or all(p["action"] == "NO_WORK" for p in pages)
    status = "BLOCKED" if blocked else "NO_WORK" if no_work else "PLANNED"
    return {"chapter": chapter, "status": status, "pages": pages,
            "reasons": ["DEPENDENCY_REVIEW_REQUIRED"] if blocked else []}


def plan_combo(manga, provider, chapters, *, repair_isolated_outputs=False):
    """Plan selected chapters in input order; duplicate or unsafe IDs block."""
    if not isinstance(chapters, (list, tuple)) or not chapters:
        return {"status": "BLOCKED", "chapters": [], "reasons": ["CHAPTERS_REQUIRED"]}
    if any(not valid_chapter_id(c) for c in chapters):
        return {"status": "BLOCKED", "chapters": [], "reasons": ["INVALID_CHAPTER_SELECTION"]}
    if len(set(chapters)) != len(chapters):
        return {"status": "BLOCKED", "chapters": [], "reasons": ["INVALID_CHAPTER_SELECTION"]}
    planned = [plan_chapter(manga, provider, chapter,
                            repair_isolated_outputs=repair_isolated_outputs)
               for chapter in chapters]
    status = ("BLOCKED" if any(x["status"] == "BLOCKED" for x in planned) else
              "NO_WORK" if all(x["status"] == "NO_WORK" for x in planned) else "PLANNED")
    return {"status": status,
            "chapters": planned, "reasons": []}


def _action(item, eligible, repair_isolated_outputs=False):
    status = item["status"]
    if status == "REUSABLE":
        return {"status": "REUSED", "needed": False, "reasons": []}
    if status == "MISSING" and not eligible:
        return {"status": "NO_WORK", "needed": False, "reasons": item["reasons"]}
    if eligible and status in {"MISSING", "STALE", "UNVERIFIED"}:
        return {"status": "PLANNED", "needed": True, "reasons": item["reasons"]}
    repairable = {"ARTIFACT_NOT_FOUND", "MANIFEST_INVALID", "ARTIFACT_HASH_MISMATCH",
                  "MASK_HASH_MISMATCH"}
    if (eligible and status == "INVALID" and repair_isolated_outputs
            and item.get("reasons") and set(item["reasons"]).issubset(repairable)):
        return {"status": "PLANNED", "needed": True, "reasons": item["reasons"]}
    return {"status": "BLOCKED", "needed": False, "reasons": item["reasons"]}


def _page_action(stages):
    if any(item["status"] == "BLOCKED" for item in stages.values()):
        return "BLOCKED"
    return "PLANNED" if any(item["needed"] for item in stages.values()) else "NO_WORK"


def _glass_candidates(manga, chapter):
    folder = stage_chapter(manga, LEVEL1, chapter)
    path = folder / "json" / "level1-balloon-report.json"
    report = json.loads(path.read_text(encoding="utf-8"))
    return {row.get("source") for row in report.get("pages", []) if isinstance(row, dict)
            and (row.get("transparent_balloons") or row.get("transparent_components_deferred"))
            and valid_page_id(row.get("source"))}
