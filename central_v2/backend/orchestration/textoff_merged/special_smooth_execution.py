"""Execute Check-approved Suave pages as isolated previews."""
from pathlib import Path

from central_v2.backend.orchestration.textoff_special.artifacts import sha256
from central_v2.backend.orchestration.textoff_special.execution import preview

from .auto_cleaner_check_manifest import _write_atomic, manifest_path as check_manifest_path
from .special_smooth_input import pending_pages, selected_input
from .special_smooth_output import persist_smooth
from .final_consolidated import promote_treatment_pages
from .special_reexecution import prepare_reexecution, validate_reexecution


def execute_smooth(manga: Path, provider: str, chapters: list[str], progress,
                   *, retry: bool = False, reexecute: bool = False) -> list[dict]:
    results = []
    for chapter_index, chapter in enumerate(chapters, 1):
        groups, persisted = None, False
        try:
            if reexecute:
                prepare_reexecution(manga, provider, chapter, "gradiente_suave")
            path, digest, payload, groups = pending_pages(manga, provider, chapter, retry=retry)
            check_path = check_manifest_path(manga, chapter)
            check_hash = payload["source_check"]["sha256"]
            page_runs, page_errors = [], {}
            progress(chapter, {"stage": "smooth", "percent": 0, "completed": 0,
                               "total": len(groups), "message": "Iniciando tratamento Suave."})
            for page_index, (page, rows) in enumerate(groups.items(), 1):
                source = selected_input(manga, chapter, page)
                source.update(provider=provider, manga=manga.name, chapter=chapter)
                rois = [dict(row["box_pixels"]) for row in rows]
                run = preview(manga, {"treatment": "gradiente_suave", "level": source["level"],
                                      "chapter": chapter, "filename": source["filename"],
                                      "expected_sha256": source["sha256"], "selections": rois})
                if run.get("execution_status") != "succeeded":
                    page_errors[page] = str(run.get("error") or "Prévia Suave falhou.")
                else:
                    page_runs.append({"source": source, "run": run,
                                      "ids": [row["id"] for row in rows], "rois": rois,
                                      "special_path": path, "special_hash": digest,
                                      "check_path": check_path, "check_hash": check_hash})
                progress(chapter, {"stage": "smooth", "percent": round(page_index * 100 / len(groups)),
                                   "completed": page_index, "total": len(groups),
                                   "message": (f"Suave falhou em {page}: {page_errors[page]}"
                                               if page in page_errors else f"Suave concluído para {page}.")})
            records = (persist_smooth(manga, provider, chapter, path, digest, page_runs,
                                      check_path=check_path, check_hash=check_hash)
                       if page_runs else {})
            promote_treatment_pages(manga, chapter, "gradiente_suave", records, page_runs)
            persisted = True
            _save_status(path, digest, payload, groups, records, page_errors,
                         check_path, check_hash, retry=retry)
            outcome = ("failed" if page_errors else
                       "processed" if any(r["status"] == "processed" for r in records.values())
                       else "no_change")
            results.append({"chapter": chapter, "status": outcome, "pages": len(groups),
                            "error": "; ".join(page_errors.values()) if page_errors else None,
                            "occurrences": sum(len(rows) for rows in groups.values())})
        except Exception as exc:
            if groups is not None and not persisted:
                try:
                    failures = {page: str(exc) for page in groups}
                    _save_status(path, digest, payload, groups, {}, failures,
                                 check_path, check_hash, retry=retry)
                except (OSError, ValueError):
                    pass
            results.append({"chapter": chapter, "status": "failed", "error": str(exc)})
        progress(chapter, {"stage": "done", "percent": round(chapter_index * 100 / len(chapters)),
                           "completed": chapter_index, "total": len(chapters),
                           "message": f"Capítulo {chapter}: {results[-1]['status']}."})
    return results


def _save_status(path, expected_hash, payload, groups, records, page_errors,
                 check_path, check_hash, *, retry=False):
    if sha256(path) != expected_hash:
        raise ValueError("Manifesto Especial mudou durante a execução.")
    if sha256(check_path) != check_hash:
        raise ValueError("Check mudou durante o processamento Suave.")
    selected = {(row["page"], row["id"]) for rows in groups.values() for row in rows}
    for row in payload["treatments"]["gradiente_suave"]:
        if (row.get("page"), row.get("id")) not in selected:
            continue
        allowed = {"failed"} if retry else {"pending"}
        if row.get("status") not in allowed:
            raise ValueError("Ocorrência Suave deixou de estar elegível.")
        record = records.get(row["page"])
        row["status"] = record["status"] if record else "failed"
        if record:
            row["result"] = {"stage": "PINCEL_SUAVE", "page": row["page"],
                              "output": record["output"], "run_id": record["run_id"]}
            row.pop("error", None)
        else:
            row["error"] = page_errors.get(row["page"], "Execução Suave falhou.")
    _write_atomic(path, payload)


def validate_smooth_reexecution(manga: Path, provider: str, chapters: object) -> list[str]:
    return validate_reexecution(manga, provider, chapters, "gradiente_suave")
