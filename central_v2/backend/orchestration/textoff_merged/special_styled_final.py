"""Prepare a current-base final chapter for an Artístico transaction."""
from datetime import datetime, timezone
from pathlib import Path
import shutil

from central_v2.backend.orchestration.textoff_special.artifacts import sha256

from . import final_consolidated as final
from .final_consolidated_manifest import write_manifest
from .stages import stage_chapter


def prepare_final(manga: Path, chapter: str, page_runs: list[dict],
                  records: dict, art_stage: Path, staged: Path) -> None:
    target = stage_chapter(manga, final.STAGE, chapter, read_legacy=False).resolve()
    if not target.is_relative_to(Path(manga).resolve()) or not target.is_dir():
        raise ValueError("Consolidado Final indisponível para a reexecução Artístico.")
    shutil.copytree(target, staged)
    payload = final._load_existing(staged, manga, chapter)
    pages, history = dict(payload["pages"]), list(payload.get("history", []))
    for item in page_runs:
        page, source = item["source"]["page"], item["source"]
        record = records.get(page)
        current = pages.get(page)
        if not record or not current or current.get("sha256") != source["sha256"]:
            raise ValueError(f"Base vigente divergente para a página {page}.")
        output_ref = record["output"]["artifact"]
        output = (art_stage / output_ref).resolve()
        if not output.is_file() or sha256(output) != record["output"]["sha256"]:
            raise ValueError(f"Composição Artístico persistida inválida para {page}.")
        history.append({"page": page, "superseded": current,
                        "superseded_at": datetime.now(timezone.utc).isoformat()})
        destination = staged / page
        shutil.copyfile(output, destination)
        digest = sha256(destination)
        if digest != record["output"]["sha256"]:
            raise ValueError(f"Composição final divergente para {page}.")
        pages[page] = {"page": page, "artifact": page, "sha256": digest,
            "origin": "PINCEL_ARTISTICO", "treatment": "estilizado",
            "input_sha256": source["sha256"], "input_origin": source["selected_from"],
            "input_manifest_sha256": source["consolidated_manifest_sha256"],
            "run_id": record.get("run_id"), "status": record["status"]}
    write_manifest(staged, final._payload(manga, chapter, pages, history,
                                         payload["source_intermediate_manifest_sha256"]))
