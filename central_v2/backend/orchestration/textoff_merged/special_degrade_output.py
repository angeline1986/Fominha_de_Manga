"""Validate staged Degradê previews and atomically publish chapter artifacts."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile

from central_v2.backend.orchestration.textoff_special.artifacts import contained_file, sha256
from central_v2.backend.orchestration.textoff_special.catalog import STAGING_ROOT
from central_v2.backend.orchestration.textoff_special.catalog import treatment_for

from .artifact_paths import artifact_ref, prepare_artifact_dirs
from .level2_validation import promote_stage
from .stages import stage_chapter
from .special_write_proof import persist_write_mask

STAGE = "PINCEL_DEGRADE"
MANIFEST = "degrade-manifest.json"
SCHEMA = "textoff_pincel_degrade_manifest_v1"


def _validated_preview(run: dict, source: dict) -> Path:
    if run.get("execution_status") != "succeeded":
        raise RuntimeError(str(run.get("error") or "Prévia Degradê falhou."))
    treatment = run.get("treatment") or {}
    if (not isinstance(treatment, dict)
            or treatment.get("algorithm") != treatment_for("degrade").algorithm
            or run.get("source", {}).get("sha256") != source["sha256"]
            or run.get("approved_check_rois") is not True):
        raise ValueError("Prévia não corresponde à entrada Consolidada.")
    identifier = run.get("run_id")
    if not isinstance(identifier, str) or not identifier.isalnum():
        raise ValueError("Identidade da prévia Degradê inválida.")
    folder = STAGING_ROOT.resolve() / identifier
    result = contained_file(folder, run.get("result_file"))
    expected = (run.get("validation") or {}).get("result_sha256")
    if not isinstance(expected, str) or sha256(result) != expected:
        raise ValueError("Resultado da prévia Degradê não confere com a validação.")
    changed = (run.get("validation") or {}).get("changed_pixels")
    if type(changed) is not int or changed < 0:
        raise ValueError("Contagem de pixels alterados inválida.")
    return result


def persist_degrade(manga: Path, provider: str, chapter: str,
                    special_path: Path, special_hash: str,
                    page_runs: list[dict]) -> dict:
    target = stage_chapter(manga, STAGE, chapter, read_legacy=False).resolve()
    if not target.is_relative_to(manga.resolve()):
        raise ValueError("Destino Degradê fora da obra.")
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f".degrade-{chapter}-", dir=target.parent) as work:
        staged = Path(work) / "stage"
        if target.exists():
            shutil.copytree(target, staged)
        else:
            prepare_artifact_dirs(staged)
        manifest_path = staged / artifact_ref("json", MANIFEST)
        if manifest_path.is_file():
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            if payload.get("schema") != SCHEMA or payload.get("chapter") != chapter:
                raise ValueError("Manifesto persistente de Degradê incompatível.")
        else:
            payload = {"schema": SCHEMA, "version": 1, "provider": provider,
                       "manga": manga.name, "chapter": chapter,
                       "treatment": "degrade", "pages": {}}
        records = {}
        for item in page_runs:
            source, run = item["source"], item["run"]
            result = _validated_preview(run, source)
            page = source["page"]
            input_ref = f"input/{run['run_id']}/{Path(page).name}"
            saved_input = staged / input_ref
            saved_input.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source["path"], saved_input)
            if sha256(saved_input) != source["sha256"]:
                raise ValueError("Snapshot persistido da entrada Degradê divergente.")
            output_ref = artifact_ref("clean", Path(page).stem + "_degrade.png")
            output = staged / output_ref
            output.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(result, output)
            output_hash = sha256(output)
            if output_hash != run["validation"]["result_sha256"]:
                raise ValueError("Cópia persistente do Degradê divergente.")
            status = "processed" if run["validation"]["changed_pixels"] else "no_change"
            records[page] = {
                "provider": provider, "manga": manga.name, "chapter": chapter,
                "page": page, "treatment": "degrade", "status": status,
                "occurrence_ids": item["ids"], "rois": item["rois"],
                "selected_from": source["selected_from"],
                "input": {"path": source["path"], "sha256": source["sha256"]},
                "input_artifact": {"artifact": input_ref, "sha256": source["sha256"]},
                "consolidated_manifest": {
                    "path": source["consolidated_manifest"],
                    "sha256": source["consolidated_manifest_sha256"]},
                "special_manifest": {"path": str(special_path), "sha256": special_hash},
                "output": {"artifact": output_ref, "sha256": output_hash},
                "run_id": run["run_id"], "changed_pixels": run["validation"]["changed_pixels"],
            }
            write_mask = persist_write_mask(staged, run, page)
            if write_mask:
                records[page]["write_mask"] = write_mask
            payload["pages"][page] = records[page]
        manifest_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        if sha256(special_path) != special_hash:
            raise ValueError("Manifesto Especial mudou durante o processamento.")
        for item in page_runs:
            source = item["source"]
            if (sha256(Path(source["path"])) != source["sha256"]
                    or sha256(Path(source["consolidated_manifest"]))
                    != source["consolidated_manifest_sha256"]):
                raise ValueError("Entrada Consolidada mudou durante o processamento.")
        promote_stage(staged, target)
    return records
