"""Run Artístico reexecution entirely in staged artifacts before publication."""
import json
from pathlib import Path
import shutil

from central_v2.backend.orchestration.textoff_special.artifacts import sha256
from central_v2.backend.orchestration.textoff_special.catalog import STAGING_ROOT
from central_v2.backend.orchestration.textoff_special.execution import preview

from .auto_cleaner_check_manifest import _write_atomic, manifest_path as check_path
from .final_consolidated import final_manifest_path, read_final_page
from .special_degrade_input import selected_input
from .special_styled_composition import compose_occurrence
from .special_styled_final import prepare_final
from .special_styled_input import pending_pages
from .special_styled_occurrence_input import occurrence_input
from .special_styled_output import MANIFEST as ART_MANIFEST, STAGE as ART_STAGE
from .special_styled_output import prepare_styled_stage
from .special_styled_plan import build_plan
from .special_styled_transaction import begin, discard_staging, publish
from .stages import stage_chapter


def execute(manga: Path, provider: str, chapters: list[str], progress,
            selections: dict[str, list[dict]]) -> list[dict]:
    if (not isinstance(selections, dict) or set(selections) != set(chapters)
            or any(not isinstance(items, list) or len(items) != 1 for items in selections.values())):
        raise ValueError("Selecione uma ocorrência Artístico por capítulo.")
    results = []
    for index, chapter in enumerate(chapters, 1):
        folder = None
        try:
            result, folder = _execute_chapter(manga, provider, chapter, progress,
                                               selections[chapter])
            results.append(result)
        except Exception as exc:
            results.append({"chapter": chapter, "status": "failed", "error": str(exc)})
        finally:
            if folder:
                discard_staging(folder)
            progress(chapter, {"stage": "done", "percent": round(index * 100 / len(chapters)),
                "completed": index, "total": len(chapters),
                "message": f"Capítulo {chapter}: {results[-1]['status']}."})
    return results


def _execute_chapter(manga, provider, chapter, progress, selected):
    plan = build_plan(manga, provider, chapter, selected)
    path, special_hash, payload, groups = pending_pages(
        manga, provider, chapter, payload_override=plan["payload"])
    chosen = {(item["page"], item["id"]) for item in selected}
    groups = {page: [row for row in rows if (page, row["id"]) in chosen]
              for page, rows in groups.items()}
    groups = {page: rows for page, rows in groups.items() if rows}
    if len(groups) != len(selected) or any(len(rows) != 1 for rows in groups.values()):
        raise ValueError("Selecione uma ocorrência Artístico por página em cada operação.")
    historical = {page: occurrence_input(manga, chapter, page,
                  rows[0]["id"], rows[0]["box_pixels"]) for page, rows in groups.items()}
    identity, folder = begin(manga, chapter)
    try:
        check, check_hash = plan["check_path"], plan["check_hash"]
        final_manifest = final_manifest_path(manga, chapter).resolve()
        final_hash = sha256(final_manifest)
        art_folder = stage_chapter(manga, ART_STAGE, chapter, read_legacy=False).resolve()
        art_manifest = art_folder / "json" / ART_MANIFEST
        art_hash = sha256(art_manifest)
        page_runs = []
        for index, (page, rows) in enumerate(groups.items(), 1):
            detection = historical[page]
            final_record, current, current_manifest_hash = read_final_page(manga, chapter, page)
            base = selected_input(manga, chapter, page)
            base.update(provider=provider, manga=manga.name, chapter=chapter)
            if (base["sha256"] != final_record["sha256"]
                    or current_manifest_hash != final_hash):
                raise ValueError("Consolidado mudou durante a leitura para reexecução.")
            expected = next(item["expected_sha256"] for item in selected
                            if item["page"] == page and item["id"] == rows[0]["id"])
            if base["sha256"] != expected:
                raise ValueError("SHA esperado da página Artístico mudou antes da reexecução.")
            rois = [dict(row["box_pixels"]) for row in rows]
            run = preview(manga, {"treatment": "estilizado", "level": detection["level"],
                "chapter": chapter, "filename": page, "expected_sha256": detection["sha256"],
                "selections": rois}, resolved_source=detection)
            if run.get("execution_status") != "succeeded":
                raise RuntimeError(str(run.get("error") or "Prévia Artístico falhou."))
            run["run_dir"] = str(STAGING_ROOT / run["run_id"])
            composed = folder / "compositions" / f"{page}.png"
            composition = compose_occurrence(manga, chapter, page, detection, current,
                base["sha256"], final_record, run, composed)
            composition.update(base_manifest=base["consolidated_manifest"],
                               base_manifest_sha256=base["consolidated_manifest_sha256"])
            page_runs.append({"source": base, "detection_source": detection, "run": run,
                "ids": [row["id"] for row in rows], "rois": rois,
                "expected_sha256": expected,
                "special_path": path, "special_hash": special_hash,
                "check_path": check, "check_hash": check_hash,
                "composed_path": composed, "composition": composition,
                "final_record": final_record})
            progress(chapter, {"stage": "estilizado", "percent": round(index * 75 / len(groups)),
                "completed": index, "total": len(groups),
                "message": f"Artístico validado para {page}."})
        records = _prepare_artifacts(manga, provider, chapter, plan, page_runs, folder)
        _update_special(payload, groups, records)
        special_stage = folder / "stages" / "special"
        special_stage.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(path.parent, special_stage)
        _write_atomic(special_stage / path.name, payload)
        art_stage = folder / "stages" / "artistic"
        final_stage = folder / "stages" / "final"
        prepare_final(manga, chapter, page_runs, records, art_stage, final_stage)

        def validate_before_publish():
            _validate_inputs(manga, plan, special_hash, final_manifest, final_hash,
                             art_manifest, art_hash, page_runs, folder)
        entries = [{"target": str(art_folder), "staged": str(art_stage)},
                   {"target": str(stage_chapter(manga, "CONSOLIDADO_FINAL", chapter,
                       read_legacy=False).resolve()), "staged": str(final_stage)},
                   {"target": str(path.parent), "staged": str(special_stage)}]
        publish(manga, folder, entries, validate_before_publish)
        status = "processed" if any(row["status"] == "processed" for row in records.values()) else "no_change"
        return {"chapter": chapter, "status": status, "pages": len(records),
                "occurrences": sum(map(len, groups.values()))}, None
    except BaseException:
        discard_staging(folder)
        raise


def _prepare_artifacts(manga, provider, chapter, plan, page_runs, folder):
    art_stage = folder / "stages" / "artistic"
    art_stage.parent.mkdir(parents=True, exist_ok=True)
    return prepare_styled_stage(manga, provider, chapter, plan["special_path"],
        plan["special_hash"], page_runs, check_path=plan["check_path"],
        check_hash=plan["check_hash"], staged=art_stage, reexecution_id=plan["id"])


def _update_special(payload, groups, records):
    selected = {(row["page"], row["id"]) for rows in groups.values() for row in rows}
    for row in payload["treatments"]["estilizado"]:
        if (row.get("page"), row.get("id")) not in selected:
            continue
        record = records.get(row["page"])
        row["status"] = record["status"] if record else "failed"
        if record:
            row["result"] = {"stage": "PINCEL_ARTISTICO", "page": row["page"],
                "output": record["output"], "run_id": record["run_id"]}
            row.pop("error", None)
        else:
            raise ValueError("Página Artístico sem resultado persistente.")


def _validate_inputs(manga, plan, special_hash, final_manifest, final_hash,
                     art_manifest, art_hash, page_runs, folder):
    check, check_hash = plan["check_path"], plan["check_hash"]
    if (sha256(check) != check_hash or sha256(plan["special_path"]) != special_hash
            or sha256(final_manifest) != final_hash or sha256(art_manifest) != art_hash):
        raise ValueError("Check ou manifesto mudou antes da publicação Artístico.")
    for item in page_runs:
        base, detection, run = item["source"], item["detection_source"], item["run"]
        if (sha256(Path(base["path"])) != base["sha256"]
                or base["sha256"] != item["expected_sha256"]
                or sha256(Path(base["consolidated_manifest"])) != base["consolidated_manifest_sha256"]
                or sha256(Path(detection["path"])) != detection["sha256"]
                or sha256(Path(detection["prior_output"])) != detection["prior_output_sha256"]
                or sha256(Path(run["run_dir"]) / run["result_file"])
                   != (run.get("validation") or {}).get("result_sha256")
                or sha256(item["composed_path"]) != item["composition"]["composed_sha256"]):
            raise ValueError("Snapshot ou artefato Artístico mudou antes da publicação.")
        for proof in detection.get("proofs", []):
            if sha256(Path(proof["path"])) != proof["sha256"]:
                raise ValueError("Proveniência histórica Artístico mudou antes da publicação.")
        verified = folder / "revalidation" / f"{base['page']}.png"
        current = Path(base["path"])
        composition = compose_occurrence(manga, base["chapter"], base["page"], detection,
            current, base["sha256"], item["final_record"], run, verified)
        composition.update(base_manifest=base["consolidated_manifest"],
                           base_manifest_sha256=base["consolidated_manifest_sha256"])
        if composition != item["composition"]:
            raise ValueError("Composição ou linhagem Artístico mudou antes da publicação.")
