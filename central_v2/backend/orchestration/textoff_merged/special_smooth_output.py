"""Atomically publish validated Suave previews in their own stage."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile

from central_v2.backend.orchestration.textoff_special.artifacts import contained_file, sha256
from central_v2.backend.orchestration.textoff_special.catalog import STAGING_ROOT, treatment_for

from .artifact_paths import artifact_ref, prepare_artifact_dirs
from .level2_validation import promote_stage
from .stages import stage_chapter

STAGE = "PINCEL_SUAVE"
MANIFEST = "suave-manifest.json"
SCHEMA = "textoff_pincel_suave_manifest_v1"


def _validated_preview(run: dict, source: dict) -> tuple[Path, Path, int]:
    treatment = run.get("treatment") or {}
    if (run.get("execution_status") != "succeeded"
            or not isinstance(treatment, dict)
            or treatment.get("algorithm") != treatment_for("gradiente_suave").algorithm
            or run.get("source", {}).get("sha256") != source["sha256"]):
        raise ValueError(str(run.get("error") or "Prévia Suave não corresponde à entrada."))
    identifier = run.get("run_id")
    if not isinstance(identifier, str) or not identifier.isalnum():
        raise ValueError("Identidade da prévia Suave inválida.")
    folder = STAGING_ROOT.resolve() / identifier
    result = contained_file(folder, run.get("result_file"))
    expected = (run.get("validation") or {}).get("result_sha256")
    changed = (run.get("validation") or {}).get("changed_pixels")
    if not isinstance(expected, str) or sha256(result) != expected:
        raise ValueError("Resultado da prévia Suave não confere com a validação.")
    if type(changed) is not int or changed < 0:
        raise ValueError("Contagem de pixels alterados inválida.")
    report = contained_file(folder, "treatment/gradiente_suave_report.json")
    return result, report, changed


def persist_smooth(manga: Path, provider: str, chapter: str, special_path: Path,
                   special_hash: str, page_runs: list[dict], *,
                   check_path: Path, check_hash: str) -> dict:
    target = stage_chapter(manga, STAGE, chapter, read_legacy=False).resolve()
    if not target.is_relative_to(manga.resolve()):
        raise ValueError("Destino Suave fora da obra.")
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f".suave-{chapter}-", dir=target.parent) as work:
        staged = Path(work) / "stage"
        if target.exists():
            shutil.copytree(target, staged)
        else:
            prepare_artifact_dirs(staged)
        manifest_path = staged / artifact_ref("json", MANIFEST)
        payload = _load_manifest(manifest_path, provider, manga, chapter)
        records = {}
        for item in page_runs:
            source, run = item["source"], item["run"]
            result, report, changed = _validated_preview(run, source)
            page = source["page"]
            input_ref = f"input/{run['run_id']}/{Path(page).name}"
            saved_input = staged / input_ref
            saved_input.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source["path"], saved_input)
            if sha256(saved_input) != source["sha256"]:
                raise ValueError("Snapshot persistido da entrada Suave divergente.")
            output_ref = artifact_ref("clean", Path(page).stem + "_suave.png")
            report_ref = artifact_ref("json", Path(page).stem + "_gradiente_suave_report.json")
            output, saved_report = staged / output_ref, staged / report_ref
            output.parent.mkdir(parents=True, exist_ok=True)
            saved_report.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(result, output)
            shutil.copyfile(report, saved_report)
            status = "processed" if changed else "no_change"
            records[page] = _record(item, status, output_ref, sha256(output),
                                    report_ref, sha256(saved_report), changed, input_ref)
            payload["pages"][page] = records[page]
        manifest_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                                 encoding="utf-8")
        _assert_inputs(special_path, special_hash, check_path, check_hash, page_runs)
        promote_stage(staged, target)
    return records


def _load_manifest(path, provider, manga, chapter):
    if path.is_file():
        payload = json.loads(path.read_text(encoding="utf-8"))
        if (payload.get("schema") != SCHEMA or payload.get("version") != 1
                or payload.get("chapter") != chapter
                or payload.get("provider") != provider or payload.get("manga") != manga.name
                or payload.get("treatment") != "gradiente_suave"
                or payload.get("algorithm") != treatment_for("gradiente_suave").algorithm
                or not isinstance(payload.get("pages"), dict)):
            raise ValueError("Manifesto persistente Suave incompatível.")
        return payload
    return {"schema": SCHEMA, "version": 1, "provider": provider,
            "manga": manga.name, "chapter": chapter,
            "treatment": "gradiente_suave", "algorithm": treatment_for("gradiente_suave").algorithm,
            "pages": {}}


def _record(item, status, output_ref, output_hash, report_ref, report_hash, changed, input_ref):
    source, run = item["source"], item["run"]
    return {"provider": source["provider"], "manga": source["manga"],
            "chapter": source["chapter"], "page": source["page"],
            "treatment": "gradiente_suave", "algorithm": treatment_for("gradiente_suave").algorithm,
            "status": status, "occurrence_ids": item["ids"], "rois": item["rois"],
            "selected_from": source["selected_from"],
            "input": {"path": source["path"], "sha256": source["sha256"]},
            "input_artifact": {"artifact": input_ref, "sha256": source["sha256"]},
            "consolidated_manifest": {"path": source["consolidated_manifest"],
                                      "sha256": source["consolidated_manifest_sha256"]},
            "special_manifest": {"path": str(item["special_path"]),
                                 "sha256": item["special_hash"]},
            "check_manifest": {"path": str(item["check_path"]),
                               "sha256": item["check_hash"]},
            "output": {"artifact": output_ref, "sha256": output_hash},
            "report": {"artifact": report_ref, "sha256": report_hash},
            "run_id": run["run_id"], "changed_pixels": changed}


def _assert_inputs(special_path, special_hash, check_path, check_hash, page_runs):
    if sha256(special_path) != special_hash:
        raise ValueError("Manifesto Especial mudou durante o processamento.")
    if sha256(check_path) != check_hash:
        raise ValueError("Check mudou durante o processamento Suave.")
    for item in page_runs:
        source = item["source"]
        if (sha256(Path(source["path"])) != source["sha256"]
                or sha256(Path(source["consolidated_manifest"]))
                != source["consolidated_manifest_sha256"]):
            raise ValueError("Entrada Consolidada mudou durante o processamento.")
