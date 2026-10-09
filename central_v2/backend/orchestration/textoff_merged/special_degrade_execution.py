"""Run only approved pending Degradê pages through the existing V2 preview."""
from __future__ import annotations

from pathlib import Path

from central_v2.backend.orchestration.textoff_special.artifacts import sha256
from central_v2.backend.orchestration.textoff_special.execution import preview

from .auto_cleaner_check_manifest import _write_atomic, manifest_path as check_manifest_path
from .special_degrade_input import pending_pages, selected_input
from .special_degrade_output import persist_degrade
from .final_consolidated import promote_treatment_pages
from .special_reexecution import prepare_reexecution, validate_reexecution
from .special_styled_transaction import transaction_lock


def validate_degrade_chapters(manga: Path, provider: str, chapters: object,
                              *, retry: bool = False) -> list[str]:
    if (not isinstance(chapters, list) or not chapters
            or any(not isinstance(name, str) or not name or Path(name).name != name
                   or name in {".", ".."} or "\\" in name for name in chapters)
            or len(set(chapters)) != len(chapters)):
        raise ValueError("Selecione capítulos válidos sem repetição.")
    for chapter in chapters:
        pending_pages(manga, provider, chapter, retry=retry)
    return chapters


def _save_status(path: Path, expected_hash: str, payload: dict,
                 groups: dict, records: dict, error: str = "", *, retry: bool = False) -> None:
    if sha256(path) != expected_hash:
        raise ValueError("Manifesto Especial mudou durante a execução.")
    selected = {(row["page"], row["id"])
                for rows in groups.values() for row in rows}
    for row in payload["treatments"]["degrade"]:
        if (row.get("page"), row.get("id")) not in selected:
            continue
        if row.get("status") not in ({"pending", "failed"} if retry else {"pending"}):
            raise ValueError("Ocorrência Degradê deixou de estar elegível.")
        record = records.get(row["page"])
        row["status"] = record["status"] if record else "failed"
        if record:
            row["result"] = {"stage": "PINCEL_DEGRADE", "page": row["page"],
                             "output": record["output"], "run_id": record["run_id"]}
            row.pop("error", None)
        else:
            row["error"] = error
    _write_atomic(path, payload)


def execute_degrade(manga: Path, provider: str, chapters: list[str], progress,
                    *, retry: bool = False, reexecute: bool = False) -> list[dict]:
    with transaction_lock(Path(manga)):
        return _execute_degrade(manga, provider, chapters, progress,
                                retry=retry, reexecute=reexecute)


def _execute_degrade(manga, provider, chapters, progress, *, retry, reexecute):
    results = []
    for index, chapter in enumerate(chapters, 1):
        groups = None
        persisted = False
        try:
            if reexecute:
                prepare_reexecution(manga, provider, chapter, "degrade")
            path, digest, payload, groups = pending_pages(manga, provider, chapter, retry=retry)
            page_runs = []
            for page, rows in groups.items():
                source = selected_input(manga, chapter, page)
                rois = [dict(row["box_pixels"]) for row in rows]
                progress(chapter, {"stage": "degrade", "percent": 0,
                                   "completed": index - 1, "total": len(chapters),
                                   "message": f"Tratando {page} com {len(rois)} ROI(s)."})

                def report_worker(event):
                    progress(chapter, {
                        "stage": event["stage"], "percent": event["percent"],
                        "completed": index - 1, "total": len(chapters),
                        "message": f"{page}: {event['message']}",
                    })

                run = preview(manga, {"treatment": "degrade", "level": source["level"],
                                      "chapter": chapter, "filename": source["filename"],
                                      "expected_sha256": source["sha256"], "selections": rois},
                              approved_check_rois=True, on_progress=report_worker)
                if run.get("execution_status") != "succeeded":
                    raise RuntimeError(str(run.get("error") or "Prévia Degradê falhou."))
                page_runs.append({"source": source, "run": run,
                                  "ids": [row["id"] for row in rows], "rois": rois})
            check_hash = payload["source_check"]["sha256"]
            if sha256(check_manifest_path(manga, chapter)) != check_hash:
                raise ValueError("Check mudou durante o processamento Degradê.")
            records = persist_degrade(manga, provider, chapter, path, digest, page_runs)
            promote_treatment_pages(manga, chapter, "degrade", records, page_runs)
            persisted = True
            _save_status(path, digest, payload, groups, records, retry=retry)
            outcome = "processed" if any(item["status"] == "processed" for item in records.values()) else "no_change"
            results.append({"chapter": chapter, "status": outcome,
                            "pages": len(records),
                            "occurrences": sum(len(rows) for rows in groups.values())})
        except Exception as exc:
            if groups is not None and not persisted:
                try:
                    _save_status(path, digest, payload, groups, {}, str(exc), retry=retry)
                except (OSError, ValueError):
                    pass
            results.append({"chapter": chapter, "status": "failed", "error": str(exc)})
        progress(chapter, {"stage": "done", "percent": round(index * 100 / len(chapters)),
                           "completed": index, "total": len(chapters),
                           "message": f"Capítulo {chapter}: {results[-1]['status']}."})
    return results


def validate_degrade_reexecution(manga: Path, provider: str, chapters: object) -> list[str]:
    return validate_reexecution(manga, provider, chapters, "degrade")
