"""Deterministic page-level planning for the isolated Combo Turbo runner."""
import json
import time
from pathlib import Path

from central_v2.backend.operational_log import emit
from central_v2.backend.orchestration.textoff_merged.solid_stage import rows_for
from central_v2.backend.orchestration.textoff_merged.stages import LEVEL1, stage_chapter

from .models import valid_chapter_id, valid_page_id
from .validation import validate_chapter


def plan_chapter(manga, provider, chapter, *, repair_isolated_outputs=False):
    """Plan each candidate page without executing either cleaner."""
    if not valid_chapter_id(chapter):
        emit("WARNING", "capítulo bloqueado", component="COMBO", capítulo=chapter,
             motivo="INVALID_CHAPTER")
        return {"chapter": chapter, "status": "BLOCKED", "reasons": ["INVALID_CHAPTER"], "pages": []}
    root = Path(manga).resolve()
    try:
        review = validate_chapter(root, provider, chapter)
        solids_rows, _ = rows_for(root, {"provider": provider, "obra": root.name,
                                         "capitulo": chapter}, chapter)
        solid_pages = {row.get("page") for row in solids_rows if valid_page_id(row.get("page"))}
        glass_pages = _glass_candidates(root, chapter)
    except (OSError, ValueError, TypeError, KeyError, RuntimeError) as exc:
        emit("WARNING", "capítulo bloqueado", component="COMBO", capítulo=chapter,
             motivo="AUTHORITY_UNAVAILABLE", detalhe=str(exc))
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
    emit("INFO", "capítulo analisado", component="COMBO", capítulo=chapter,
         paginas=len(pages), paginas_planejadas=sum(p["action"] == "PLANNED" for p in pages),
         paginas_com_reuso=sum(any(stage["status"] == "REUSED"
                                   for stage in p["stages"].values()) for p in pages),
         paginas_bloqueadas=sum(p["action"] == "BLOCKED" for p in pages),
         paginas_sem_trabalho=sum(p["action"] == "NO_WORK" for p in pages),
         solids_reusable_artifacts=_status_count(records, "SOLIDOS", "REUSABLE"),
         glass_reusable_artifacts=_status_count(records, "GLASS", "REUSABLE"),
         solids_missing_artifacts=_status_count(records, "SOLIDOS", "MISSING"),
         glass_missing_artifacts=_status_count(records, "GLASS", "MISSING"),
         solids_unverified_artifacts=_status_count(records, "SOLIDOS", "UNVERIFIED"),
         glass_unverified_artifacts=_status_count(records, "GLASS", "UNVERIFIED"))
    if blocked:
        reasons = sorted({reason for page in pages for stage in page["stages"].values()
                          if stage["status"] == "BLOCKED" for reason in stage["reasons"]})
        emit("WARNING", "capítulo bloqueado", component="COMBO", capítulo=chapter,
             motivos=",".join(reasons) if reasons else "DEPENDENCIA_OBRIGATORIA")
    return {"chapter": chapter, "status": status, "pages": pages,
            "reasons": ["DEPENDENCY_REVIEW_REQUIRED"] if blocked else []}


def plan_combo(manga, provider, chapters, *, repair_isolated_outputs=False):
    """Plan selected chapters in input order; duplicate or unsafe IDs block."""
    started = time.monotonic()
    emit("INFO", "planejamento iniciado", component="COMBO",
         obra=Path(manga).name, capítulos=len(chapters) if isinstance(chapters, (list, tuple)) else 0)
    if not isinstance(chapters, (list, tuple)) or not chapters:
        return _finish_plan({"status": "BLOCKED", "chapters": [],
                             "reasons": ["CHAPTERS_REQUIRED"]}, started)
    if any(not valid_chapter_id(c) for c in chapters):
        return _finish_plan({"status": "BLOCKED", "chapters": [],
                             "reasons": ["INVALID_CHAPTER_SELECTION"]}, started)
    if len(set(chapters)) != len(chapters):
        return _finish_plan({"status": "BLOCKED", "chapters": [],
                             "reasons": ["INVALID_CHAPTER_SELECTION"]}, started)
    planned = [plan_chapter(manga, provider, chapter,
                            repair_isolated_outputs=repair_isolated_outputs)
               for chapter in chapters]
    status = ("BLOCKED" if any(x["status"] == "BLOCKED" for x in planned) else
              "NO_WORK" if all(x["status"] == "NO_WORK" for x in planned) else "PLANNED")
    return _finish_plan({"status": status, "chapters": planned, "reasons": []}, started)


def _finish_plan(plan, started):
    emit("INFO", "planejamento concluído", component="COMBO",
         status=plan["status"], capítulos=len(plan.get("chapters", [])),
         duração=f"{time.monotonic() - started:.1f}s")
    return plan


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


def _status_count(records, stage, status):
    return sum(item.get("status") == status for item in records[stage].values())


def _glass_candidates(manga, chapter):
    folder = stage_chapter(manga, LEVEL1, chapter)
    path = folder / "json" / "level1-balloon-report.json"
    report = json.loads(path.read_text(encoding="utf-8"))
    return {row.get("source") for row in report.get("pages", []) if isinstance(row, dict)
            and (row.get("transparent_balloons") or row.get("transparent_components_deferred"))
            and valid_page_id(row.get("source"))}
