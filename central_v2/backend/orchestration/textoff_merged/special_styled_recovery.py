"""Recover Artístico lineage only from exact manifest-linked stage artifacts."""
import json
from pathlib import Path

from central_v2.backend.orchestration.textoff_special.artifacts import sha256

from .artifact_paths import artifact_ref
from .final_consolidated import final_manifest_path
from .final_consolidated_manifest import read_manifest
from .stages import LEVEL1, LEVEL2, stage_chapter

ORIGINS = {
    "AUTO_CLEANER": (LEVEL1, "clean-manifest.json"),
    "AUTO_CLEANER_TRANSPARENCIA": (LEVEL2, "clean-manifest.json"),
    "PINCEL_DEGRADE": ("PINCEL_DEGRADE", "degrade-manifest.json"),
    "PINCEL_SUAVE": ("PINCEL_SUAVE", "suave-manifest.json"),
}


def recover_from_final_history(manga: Path, chapter: str, page: str) -> dict:
    path = final_manifest_path(manga, chapter).resolve()
    digest = sha256(path)
    payload = read_manifest(path, manga, chapter)
    history = payload.get("history", [])
    records = [item.get("superseded") for item in history
               if isinstance(item, dict) and item.get("page") == page]
    art_position = next((index for index in range(len(records) - 1, -1, -1)
                         if isinstance(records[index], dict)
                         and records[index].get("origin") == "PINCEL_ARTISTICO"), None)
    art = records[art_position] if art_position is not None else None
    if not art or not _record_identity(art, page):
        raise ValueError("Histórico Artístico verificável ausente no Consolidado Final.")
    source, source_manifest, source_manifest_hash = _resolve_source(manga, chapter, page, art)
    prior, downstream_manifest = _resolve_prior_output(
        manga, chapter, page, art, records[art_position + 1:], payload["pages"].get(page))
    if sha256(path) != digest:
        raise ValueError("Manifesto Final mudou durante a recuperação histórica Artístico.")
    proofs = [{"path": str(path), "sha256": digest},
              {"path": str(source_manifest), "sha256": source_manifest_hash}]
    if downstream_manifest:
        proofs.append({"path": str(downstream_manifest),
                       "sha256": sha256(downstream_manifest)})
    return {"path": str(source), "sha256": art["input_sha256"], "filename": page,
            "page": page, "selected_from": art["input_origin"],
            "level": "ARTISTICO_HISTORICAL_INPUT", "history_manifest": str(path),
            "history_manifest_sha256": digest,
            "historical_input_manifest_sha256": art["input_manifest_sha256"],
            "prior_output": str(prior),
            "prior_output_sha256": art["sha256"], "prior_run_id": art.get("run_id"),
            "proofs": proofs, "consolidated_manifest": str(source_manifest),
            "consolidated_manifest_sha256": source_manifest_hash}


def _record_identity(row, page):
    return (row.get("page") == page and row.get("artifact") == page
            and isinstance(row.get("sha256"), str)
            and isinstance(row.get("input_sha256"), str)
            and isinstance(row.get("input_manifest_sha256"), str)
            and isinstance(row.get("run_id"), str))


def _resolve_source(manga, chapter, page, art):
    origin = art["input_origin"]
    if origin not in ORIGINS:
        raise ValueError("Origem da entrada histórica Artístico não é recuperável.")
    stage, filename = ORIGINS[origin]
    folder = stage_chapter(manga, stage, chapter, read_legacy=False).resolve()
    manifest = (folder / artifact_ref("json", filename)).resolve()
    if not manifest.is_relative_to(folder) or not manifest.is_file():
        raise ValueError("Manifesto do estágio da entrada histórica Artístico ausente.")
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    if origin.startswith("AUTO_CLEANER"):
        artifact = artifact_ref("clean", Path(page).stem + "_clean.png")
        if (page not in payload.get("source_artifacts", [])
                or artifact not in payload.get("clean_artifacts", [])):
            raise ValueError("Manifesto não comprova a página da entrada histórica Artístico.")
    else:
        record = _find_page_record(payload, page, art["input_sha256"])
        artifact = (record.get("output") or {}).get("artifact")
    source = _safe(folder, artifact, "clean")
    if sha256(source) != art["input_sha256"]:
        raise ValueError("Hash do artefato de entrada histórica Artístico divergente.")
    return source, manifest, sha256(manifest)


def _resolve_prior_output(manga, chapter, page, art, history, current):
    digest = art["sha256"]
    if current and current.get("origin") == "PINCEL_ARTISTICO" and current.get("sha256") == digest:
        return _safe(stage_chapter(manga, "CONSOLIDADO_FINAL", chapter), page, "."), None
    for row in [*history, current or {}]:
        if not isinstance(row, dict) or row.get("input_origin") != "PINCEL_ARTISTICO":
            continue
        if row.get("input_sha256") != digest or row.get("origin") not in ORIGINS:
            continue
        stage, filename = ORIGINS[row["origin"]]
        folder = stage_chapter(manga, stage, chapter, read_legacy=False).resolve()
        manifest = folder / artifact_ref("json", filename)
        if not manifest.is_file():
            continue
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        record = _find_page_record(payload, page, digest, row.get("run_id"), input=True)
        if ((record.get("output") or {}).get("sha256") != row.get("sha256")
                or record.get("run_id") != row.get("run_id")):
            raise ValueError("Linhagem do snapshot Artístico posterior diverge do Consolidado Final.")
        artifact = (record.get("input_artifact") or {}).get("artifact")
        try:
            prior = _safe(folder, artifact, "input")
        except ValueError:
            continue
        if sha256(prior) == digest:
            return prior, manifest
    raise ValueError("Saída Artística anterior ausente; reexecução bloqueada antes da publicação.")


def _find_page_record(payload, page, digest, run_id=None, input=False):
    rows = [((payload.get("pages") or {}).get(page) or {})]
    for group in payload.get("superseded_results", []):
        rows.extend(item.get("record") or {} for item in group.get("pages", []))
    for row in rows:
        info = row.get("input_artifact") if input else row.get("output")
        if (isinstance(info, dict) and info.get("sha256") == digest
                and (run_id is None or row.get("run_id") == run_id)):
            return row
    raise ValueError("Manifesto de tratamento não comprova o artefato histórico.")


def _safe(folder, reference, section):
    relative = Path(reference) if isinstance(reference, str) else Path()
    path = (Path(folder) / relative).resolve()
    root = (Path(folder).resolve() / section).resolve()
    if (not isinstance(reference, str) or relative.is_absolute() or ".." in relative.parts
            or not path.is_relative_to(root) or not path.is_file()):
        raise ValueError("Artefato histórico fora do estágio esperado ou ausente.")
    return path
