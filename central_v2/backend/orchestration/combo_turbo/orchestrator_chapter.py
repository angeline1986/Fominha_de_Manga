"""Run and summarize one chapter within an isolated Combo workspace."""
from pathlib import Path

from .execution import (glass_images, level1_image, run_glass_isolated,
                        run_solids_isolated, solid_image)
from .orchestrator_composition import _compose_or_reuse
from .validation import validate_page


def _run_chapter(manga, provider, chapter, plan, destination, progress, page_callback=None):
    pages = [row["page"] for row in plan["pages"]]
    actions = {stage: {row["page"]: row["stages"][stage]
                       for row in plan["pages"]} for stage in ("SOLIDOS", "GLASS")}
    errors = []
    solid_pending = [page for page, item in actions["SOLIDOS"].items() if item["needed"]]
    solid_reusable = [page for page, item in actions["SOLIDOS"].items()
                      if item["status"] == "REUSED"]
    if solid_pending:
        try:
            run_solids_isolated(manga, provider, chapter, solid_pending, solid_reusable)
            _notify(progress, {"chapter": chapter, "stage": "SOLIDOS", "status": "COMPLETED"})
        except (OSError, ValueError, RuntimeError) as exc:
            errors.append({"stage": "SOLIDOS", "reason": "EXECUTION_FAILED", "detail": str(exc)})
    glass_pending = [page for page, item in actions["GLASS"].items() if item["needed"]]
    glass_reusable = [page for page, item in actions["GLASS"].items()
                      if item["status"] == "REUSED"]
    if glass_pending and not errors:
        try:
            errors.extend(run_glass_isolated(manga, provider, chapter, glass_pending,
                                             glass_reusable, progress))
        except (OSError, ValueError, TypeError, RuntimeError) as exc:
            errors.append({"stage": "GLASS", "reason": "EXECUTION_FAILED", "detail": str(exc)})
    outcomes = []
    planned_by_page = {row["page"]: row for row in plan["pages"]}
    failed_stages = {row.get("stage") for row in errors}
    for page in pages:
        _notify(progress, {"chapter": chapter, "page": page, "stage": "validation", "status": "RUNNING"})
        solid = validate_page(manga, provider, chapter, page, "SOLIDOS")
        glass = validate_page(manga, provider, chapter, page, "GLASS")
        l1 = level1_image(manga, chapter, page)
        solids_path = solid_image(manga, chapter, page) if solid["status"] == "REUSABLE" else None
        glass_path, mask_path = glass_images(manga, chapter, page) if glass["status"] == "REUSABLE" else (None, None)
        _notify(progress, {"chapter": chapter, "page": page,
                           "stage": "COMPOSING", "status": "RUNNING"})
        composed = _compose_or_reuse(manga, provider, chapter, page, l1,
            destination / "composed" / chapter, solids_path, glass_path, mask_path, solid, glass)
        outcome = {"page": page, "solids": solid, "glass": glass,
                   "composition": composed, "status": composed["status"]}
        needed_failed = any(failed_stages.intersection({stage})
            and planned_by_page[page]["stages"][stage].get("needed")
            for stage in ("SOLIDOS", "GLASS"))
        if needed_failed and outcome["status"] == "NO_WORK":
            outcome["status"] = "FAILED"
            outcome["reasons"] = ["REQUIRED_STAGE_FAILED"]
        outcomes.append(outcome)
        if callable(page_callback):
            page_callback(outcome, planned_by_page[page])
        _notify(progress, {"chapter": chapter, "page": page, "stage": "complete",
                           "status": outcome["status"]})
    state = "NO_WORK" if not outcomes or all(row["status"] == "NO_WORK"
                                              for row in outcomes) else "PARTIAL" if errors or any(row["status"] in
                                      {"BLOCKED", "INVALID", "CONFLICT", "FAILED"}
                                      for row in outcomes) else "COMPLETED"
    _notify(progress, {"chapter": chapter, "stage": "chapter_complete", "status": state})
    return {"chapter": chapter, "status": state, "pages": outcomes, "errors": errors}


def _notify(callback, event):
    if callable(callback):
        callback(event)


def _count_states(pages):
    states = {key: 0 for key in ("COMPOSED", "NO_WORK", "CONFLICT", "BLOCKED", "FAILED")}
    for row in pages:
        state = row.get("status")
        states[state if state in states else "FAILED"] += 1
    return states


def _run_status(results, errors):
    if not results or all(row.get("status") == "NO_WORK" for row in results):
        return "NO_WORK"
    if errors or any(row.get("status") in {"PARTIAL", "BLOCKED", "FAILED"}
                     or any(value for key, value in row.get("counts", {}).items()
                             if key in {"CONFLICT", "BLOCKED", "FAILED"})
                     for row in results):
        return "PARTIAL"
    return "COMPLETED"
