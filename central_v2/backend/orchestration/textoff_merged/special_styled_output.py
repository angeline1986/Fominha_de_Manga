"""Persist validated Artístico previews and immutable input snapshots."""
import json
from pathlib import Path
import shutil
import tempfile

from central_v2.backend.orchestration.textoff_special.artifacts import contained_file, sha256
from central_v2.backend.orchestration.textoff_special.catalog import STAGING_ROOT, treatment_for

from .artifact_paths import artifact_ref, prepare_artifact_dirs
from .level2_validation import promote_stage
from .stages import stage_chapter
from .special_styled_authorship import persist as persist_authorship

STAGE = "PINCEL_ARTISTICO"
MANIFEST = "artistico-manifest.json"
SCHEMA = "textoff_pincel_artistico_manifest_v1"


def _validated_preview(run, source):
    if (run.get("execution_status") != "succeeded"
            or (run.get("treatment") or {}).get("algorithm") != treatment_for("estilizado").algorithm
            or (run.get("source") or {}).get("sha256") != source["sha256"]):
        raise ValueError(str(run.get("error") or "Prévia Artístico não corresponde à entrada."))
    run_id = run.get("run_id")
    if not isinstance(run_id, str) or not run_id.isalnum():
        raise ValueError("Identidade da prévia Artístico inválida.")
    folder = STAGING_ROOT.resolve() / run_id
    result = contained_file(folder, run.get("result_file"))
    report = contained_file(folder, "treatment/roi_report.json")
    expected = (run.get("validation") or {}).get("result_sha256")
    changed = (run.get("validation") or {}).get("changed_pixels")
    if not isinstance(expected, str) or sha256(result) != expected:
        raise ValueError("Resultado da prévia Artístico diverge da validação.")
    if type(changed) is not int or changed < 0:
        raise ValueError("Contagem de pixels alterados inválida.")
    return result, report, changed


def persist_styled(manga: Path, provider: str, chapter: str, special_path: Path,
                   special_hash: str, page_runs: list[dict], *,
                   check_path: Path, check_hash: str) -> dict:
    target = stage_chapter(manga, STAGE, chapter, read_legacy=False).resolve()
    if not target.is_relative_to(manga.resolve()):
        raise ValueError("Destino Artístico fora da obra.")
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f".artistico-{chapter}-", dir=target.parent) as work:
        staged = Path(work) / "stage"
        records = prepare_styled_stage(manga, provider, chapter, special_path, special_hash,
            page_runs, check_path=check_path, check_hash=check_hash, staged=staged)
        promote_stage(staged, target)
    return records


def prepare_styled_stage(manga, provider, chapter, special_path, special_hash,
                         page_runs, *, check_path, check_hash, staged,
                         reexecution_id=None):
    """Build an unpublished Artístico directory for a coordinated transaction."""
    target = stage_chapter(manga, STAGE, chapter, read_legacy=False).resolve()
    if target.exists():
        shutil.copytree(target, staged)
    else:
        prepare_artifact_dirs(staged)
    manifest = staged / artifact_ref("json", MANIFEST)
    payload = _load_manifest(manifest, provider, manga, chapter)
    if reexecution_id:
        _archive_previous(staged, payload, reexecution_id, check_hash,
                          {item["source"]["page"] for item in page_runs})
    records = {}
    for item in page_runs:
        source, run = item.get("detection_source", item["source"]), item["run"]
        result, report, changed = _validated_preview(run, source)
        page, run_id = source["filename"], run["run_id"]
        input_ref = f"input/{run_id}/{Path(page).name}"
        saved_input = staged / input_ref
        saved_input.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source["path"], saved_input)
        if sha256(saved_input) != source["sha256"]:
            raise ValueError("Snapshot persistido da entrada Artístico divergente.")
        output_ref = artifact_ref("clean", Path(page).stem + "_artistico.png")
        report_ref = artifact_ref("json", Path(page).stem + "_artistico_report.json")
        output, saved_report = staged / output_ref, staged / report_ref
        shutil.copyfile(item.get("composed_path", result), output)
        shutil.copyfile(report, saved_report)
        record = _record(item, "processed" if changed else "no_change", output_ref,
            sha256(output), report_ref, sha256(saved_report), changed, input_ref,
            provider, manga.name, chapter)
        mask_ref = ((run.get("treatment") or {}).get("artifacts") or {}).get("authorized_mask")
        authorized = contained_file(STAGING_ROOT.resolve() / run_id, f"treatment/{mask_ref}")
        expected_mask = (run.get("artifacts") or {}).get(f"treatment/{mask_ref}")
        if sha256(authorized) != expected_mask:
            raise ValueError("Máscara da prévia Artístico sem hash verificável.")
        ownership = persist_authorship(staged, source["path"], result, authorized,
                                        item["ids"], item["rois"], run_id)
        for proof in ownership.values():
            proof["filter"] = {"algorithm": run["treatment"]["algorithm"],
                               "configuration": {"selection": proof["roi"]}}
        if reexecution_id:
            old = (payload.get("_previous_pages") or {}).get(page)
            if not isinstance(old, dict):
                raise ValueError("Resultado anterior da página Artístico ausente.")
            record["occurrence_ids"] = old["occurrence_ids"]
            record["rois"] = old["rois"]
            previous = old.get("occurrences") or {}
            if not isinstance(previous, dict) or any(identity not in previous for identity in old["occurrence_ids"]):
                raise ValueError("Autoria das demais ocorrências Artístico insuficiente.")
            record["occurrences"] = {**previous, **ownership}
            record["dependencies"] = item["composition"].get("dependencies", [])
        else:
            record["occurrences"] = ownership
        if item.get("composition"):
            technical_ref = f"clean/technical/{run_id}_{Path(page).stem}.png"
            technical = staged / technical_ref
            technical.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(result, technical)
            record["technical_output"] = {"artifact": technical_ref, "sha256": sha256(technical)}
            record["composition"] = item["composition"]
        payload["pages"][page] = record
        records[page] = record
    payload.pop("_previous_pages", None)
    manifest.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _assert_inputs(special_path, special_hash, check_path, check_hash, page_runs)
    return records


def _archive_previous(staged, payload, identity, check_hash, selected_pages):
    pages, archived_pages = payload.get("pages", {}), []
    payload["_previous_pages"] = {page: pages[page] for page in selected_pages if page in pages}
    for page in selected_pages:
        record = pages.get(page)
        if not isinstance(record, dict):
            raise ValueError("Página Artístico anterior ausente para arquivamento.")
        files = []
        for key in ("output", "report"):
            info = record.get(key) or {}
            ref = info.get("artifact")
            if not ref:
                continue
            source = (staged / ref).resolve()
            if not source.is_relative_to(staged) or not source.is_file() or sha256(source) != info.get("sha256"):
                raise ValueError("Resultado anterior Artístico inválido para arquivamento.")
            target_ref = f"archive/{identity}/{ref}"
            target = staged / target_ref
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            source.unlink()
            files.append({"artifact": target_ref, "sha256": sha256(target)})
        archived_pages.append({"page": page, "record": record, "archived_artifacts": files})
    if archived_pages:
        payload.setdefault("superseded_results", []).append({"id": identity,
            "treatment": "estilizado", "check_sha256": check_hash,
            "pages": archived_pages})
    payload["pages"] = {page: record for page, record in pages.items()
                        if page not in selected_pages}


def _load_manifest(path, provider, manga, chapter):
    if path.is_file():
        payload = json.loads(path.read_text(encoding="utf-8"))
        if (payload.get("schema") != SCHEMA or payload.get("version") != 1
                or payload.get("provider") != provider or payload.get("manga") != manga.name
                or payload.get("chapter") != chapter or payload.get("treatment") != "estilizado"
                or payload.get("algorithm") != treatment_for("estilizado").algorithm
                or not isinstance(payload.get("pages"), dict)):
            raise ValueError("Manifesto persistente Artístico incompatível.")
        return payload
    return {"schema": SCHEMA, "version": 1, "provider": provider, "manga": manga.name,
            "chapter": chapter, "treatment": "estilizado",
            "algorithm": treatment_for("estilizado").algorithm, "pages": {}}


def _record(item, status, output, output_hash, report, report_hash, changed, input_ref,
            provider, manga, chapter):
    source, run = item.get("detection_source", item["source"]), item["run"]
    base = item["source"]
    consolidated = source if source.get("consolidated_manifest") else base
    return {"provider": provider, "manga": manga, "chapter": chapter, "page": source["page"],
            "treatment": "estilizado", "algorithm": treatment_for("estilizado").algorithm,
            "status": status, "occurrence_ids": item["ids"], "rois": item["rois"],
            "selected_from": source.get("selected_from"),
            "input": {"path": source["path"], "sha256": source["sha256"]},
            "input_artifact": {"artifact": input_ref, "sha256": source["sha256"]},
            "consolidated_manifest": {"path": consolidated["consolidated_manifest"],
                                      "sha256": consolidated["consolidated_manifest_sha256"]},
            "special_manifest": {"path": str(item["special_path"]), "sha256": item["special_hash"]},
            "check_manifest": {"path": str(item["check_path"]), "sha256": item["check_hash"]},
            "output": {"artifact": output, "sha256": output_hash},
            "report": {"artifact": report, "sha256": report_hash},
            "run_id": run["run_id"], "changed_pixels": changed}


def _assert_inputs(special_path, special_hash, check_path, check_hash, page_runs):
    if sha256(special_path) != special_hash or sha256(check_path) != check_hash:
        raise ValueError("Check ou Manifesto Especial mudou durante Artístico.")
    for item in page_runs:
        source = item["source"]
        if (sha256(Path(source["path"])) != source["sha256"]
                or sha256(Path(source["consolidated_manifest"]))
                != source["consolidated_manifest_sha256"]):
            raise ValueError("Entrada vigente mudou durante Artístico.")
