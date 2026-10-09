"""Execute Check-approved styled-balloon ROIs against current final pages."""
from pathlib import Path
import json
import re

from central_v2.backend.orchestration.textoff_special.artifacts import sha256
from central_v2.backend.orchestration.textoff_special.catalog import STAGING_ROOT
from central_v2.backend.orchestration.textoff_special.execution import preview

from .auto_cleaner_check_manifest import _write_atomic, manifest_path as check_manifest_path
from .final_consolidated import read_final_page
from .special_reexecution import validate_reexecution
from .special_styled_input import pending_pages, selected_input
from .special_styled_source import detection_input
from .special_styled_initial_composition import compose_initial
from .special_styled_initial_publication import publish_initial
from .special_styled_occurrence_input import occurrence_input
from .special_styled_plan import build_plan
from .special_treatments_manifest import manifest_path as special_manifest_path
from .special_styled_transaction import begin, discard_staging, transaction_lock


def execute_styled(manga: Path, provider: str, chapters: list[str], progress,
                   *, retry=False, reexecute=False, selections=None) -> list[dict]:
    if reexecute:
        if retry:
            raise ValueError("Reexecutar e tentar novamente são operações distintas.")
        from .special_styled_reexecution import execute as execute_reexecution
        return execute_reexecution(manga, provider, chapters, progress, selections)
    if selections is not None and (not isinstance(selections, dict)
                                   or set(selections) != set(chapters)):
        raise ValueError("Seleção Artístico incompleta para os capítulos solicitados.")
    return _execute_new(manga, provider, chapters, progress, retry=retry,
                        selections=selections)


def _execute_new(manga, provider, chapters, progress, *, retry, selections=None):
    results = []
    for chapter_index, chapter in enumerate(chapters, 1):
        groups, persisted, folder = None, False, None
        try:
            path, digest, payload, groups = pending_pages(manga, provider, chapter,
                retry=retry, selections=selections.get(chapter) if selections is not None else None)
            check_path = check_manifest_path(manga, chapter)
            check_hash = payload["source_check"]["sha256"]
            page_runs = []
            _identity, folder = begin(manga, chapter)
            for page_index, (page, rows) in enumerate(groups.items(), 1):
                source = selected_input(manga, chapter, page)
                source.update(provider=provider, manga=manga.name, chapter=chapter)
                final_record, current, _manifest_hash = read_final_page(manga, chapter, page)
                rois = [dict(row["box_pixels"]) for row in rows]
                detection = detection_input(manga, provider, chapter, page,
                                            rows[0]["id"], rois[0])
                for row in rows[1:]:
                    other = detection_input(manga, provider, chapter, page,
                                            row["id"], row["box_pixels"])
                    if other["sha256"] != detection["sha256"]:
                        raise ValueError("Ocorrências Artístico não compartilham entrada verificada.")
                run = preview(manga, {"treatment": "estilizado", "level": detection["level"],
                    "chapter": chapter, "filename": detection["artifact_filename"],
                    "expected_sha256": detection["sha256"], "selections": rois})
                if run.get("execution_status") != "succeeded":
                    raise RuntimeError(str(run.get("error") or "Prévia Artístico falhou."))
                run["run_dir"] = str(STAGING_ROOT / run["run_id"])
                composed = folder / "compositions" / page
                composition = compose_initial(manga, chapter, page, detection, current,
                                               final_record, run, composed)
                composition.update(base_manifest=source["consolidated_manifest"],
                                   base_manifest_sha256=source["consolidated_manifest_sha256"])
                page_runs.append({"source": source, "detection_source": detection,
                    "run": run, "composed_path": composed, "composition": composition,
                    "final_record": final_record,
                    "ids": [row["id"] for row in rows], "rois": rois,
                    "special_path": path, "special_hash": digest,
                    "check_path": check_path, "check_hash": check_hash})
                progress(chapter, {"stage": "estilizado",
                    "percent": round(page_index * 100 / len(groups)),
                    "completed": page_index, "total": len(groups),
                    "message": f"Artístico validado para {page}."})
            if sha256(check_path) != check_hash:
                raise ValueError("Check mudou durante o processamento Artístico.")
            records = publish_initial(manga, provider, chapter, path, digest, payload,
                groups, check_path, check_hash, page_runs, folder)
            persisted = True
            status = "processed" if any(row["status"] == "processed" for row in records.values()) else "no_change"
            results.append({"chapter": chapter, "status": status, "pages": len(records),
                            "occurrences": sum(map(len, groups.values()))})
        except Exception as exc:
            if groups is not None and not persisted:
                try:
                    with transaction_lock(Path(manga)):
                        _save_status(path, digest, payload, groups, {}, str(exc), retry=retry)
                except (OSError, ValueError):
                    pass
            results.append({"chapter": chapter, "status": "failed", "error": str(exc)})
        finally:
            if folder is not None:
                discard_staging(folder)
        progress(chapter, {"stage": "done", "percent": round(chapter_index * 100 / len(chapters)),
                           "completed": chapter_index, "total": len(chapters),
                           "message": f"Capítulo {chapter}: {results[-1]['status']}."})
    return results


def _save_status(path, expected_hash, payload, groups, records, error="", *, retry=False):
    if sha256(path) != expected_hash:
        raise ValueError("Manifesto Especial mudou durante a execução Artístico.")
    selected = {(row["page"], row["id"]) for rows in groups.values() for row in rows}
    for row in payload["treatments"]["estilizado"]:
        if (row.get("page"), row.get("id")) not in selected:
            continue
        if row.get("status") not in ({"pending", "failed"} if retry else {"pending"}):
            raise ValueError("Ocorrência Artístico deixou de estar elegível.")
        record = records.get(row["page"])
        row["status"] = record["status"] if record else "failed"
        if record:
            row["result"] = {"stage": "PINCEL_ARTISTICO", "page": row["page"],
                              "output": record["output"], "run_id": record["run_id"]}
            row.pop("error", None)
        else:
            row["error"] = error
    _write_atomic(path, payload)


def validate_styled_reexecution(manga: Path, provider: str, chapters: object,
                                selections: object) -> dict[str, list[dict]]:
    selected = validate_reexecution(manga, provider, chapters, "estilizado")
    if (not isinstance(selections, list) or len(selections) != len(selected)
            or any(not isinstance(item, dict) or set(item) !=
                   {"chapter", "page", "id", "expected_sha256"}
                   or any(not isinstance(item[key], str) or not item[key]
                          for key in ("chapter", "page", "id"))
                   or not isinstance(item["expected_sha256"], str)
                   or not re.fullmatch(r"[0-9a-f]{64}", item["expected_sha256"])
                   for item in selections)):
        raise ValueError("Selecione uma ocorrência Artístico por capítulo com SHA esperado.")
    result = {}
    from .final_consolidated import read_final_page
    for chapter in selected:
        matching = [item for item in selections if item.get("chapter") == chapter]
        if len(matching) != 1:
            raise ValueError("Selecione exatamente uma ocorrência Artístico por capítulo.")
        item = matching[0]
        payload = json.loads(special_manifest_path(manga, chapter).read_text(encoding="utf-8"))
        rows = payload["treatments"]["estilizado"]
        row = next((row for row in rows if row.get("page") == item["page"]
                    and row.get("id") == item["id"]), None)
        if not row or row.get("status") not in {"processed", "no_change"}:
            raise ValueError("Ocorrência Artístico não elegível para reexecução.")
        _record, current, _hash = read_final_page(manga, chapter, item["page"])
        if sha256(current) != item["expected_sha256"]:
            raise ValueError("SHA do Consolidado alterado antes da reexecução Artístico.")
        occurrence_input(manga, chapter, item["page"], item["id"], row["box_pixels"])
        result[chapter] = [{key: item[key] for key in ("page", "id", "expected_sha256")}]
        build_plan(manga, provider, chapter, result[chapter])
    return result
