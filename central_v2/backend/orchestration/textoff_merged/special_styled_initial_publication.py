"""Publish an initial Artístico result through the existing recoverable transaction."""
from pathlib import Path
import shutil

from central_v2.backend.orchestration.textoff_special.artifacts import sha256

from .auto_cleaner_check_manifest import _write_atomic
from .final_consolidated import final_manifest_path
from .special_styled_initial_composition import compose_initial
from .special_styled_final import prepare_final
from .special_styled_output import prepare_styled_stage
from .special_styled_transaction import publish
from .stages import stage_chapter


def publish_initial(manga, provider, chapter, path, digest, payload, groups,
                    check_path, check_hash, page_runs, folder):
    art_target = stage_chapter(manga, "PINCEL_ARTISTICO", chapter, read_legacy=False).resolve()
    final_target = stage_chapter(manga, "CONSOLIDADO_FINAL", chapter, read_legacy=False).resolve()
    final_manifest = final_manifest_path(manga, chapter).resolve()
    final_hash = sha256(final_manifest)
    art_stage = folder / "stages/artistic"
    art_stage.parent.mkdir(parents=True, exist_ok=True)
    records = prepare_styled_stage(manga, provider, chapter, path, digest, page_runs,
                                   check_path=check_path, check_hash=check_hash, staged=art_stage)
    final_stage = folder / "stages/final"
    prepare_final(manga, chapter, page_runs, records, art_stage, final_stage)
    special_stage = folder / "stages/special"
    shutil.copytree(path.parent, special_stage)
    selected = {(row["page"], row["id"]) for rows in groups.values() for row in rows}
    for row in payload["treatments"]["estilizado"]:
        if (row["page"], row["id"]) not in selected:
            continue
        record = records[row["page"]]
        row["status"] = record["status"]
        row["result"] = {"stage": "PINCEL_ARTISTICO", "page": row["page"],
                         "output": record["output"], "run_id": record["run_id"]}
        row.pop("error", None)
    _write_atomic(special_stage / path.name, payload)

    def validate():
        if (sha256(path) != digest or sha256(check_path) != check_hash
                or sha256(final_manifest) != final_hash):
            raise ValueError("Check, Especial ou Consolidado mudou antes da publicação Artístico.")
        for item in page_runs:
            current, detection, run = item["source"], item["detection_source"], item["run"]
            if (sha256(Path(current["path"])) != current["sha256"]
                    or sha256(Path(detection["path"])) != detection["sha256"]
                    or sha256(Path(detection["consolidated_manifest"]))
                       != detection["consolidated_manifest_sha256"]
                    or sha256(Path(current["consolidated_manifest"]))
                       != current["consolidated_manifest_sha256"]):
                raise ValueError("Entrada Artístico mudou antes da publicação.")
            verification = folder / "revalidation" / item["source"]["page"]
            proof = compose_initial(manga, chapter, current["page"], detection,
                Path(current["path"]), item["final_record"], run, verification)
            proof.update(base_manifest=current["consolidated_manifest"],
                         base_manifest_sha256=current["consolidated_manifest_sha256"])
            if proof != item["composition"]:
                raise ValueError("Autoria Artístico mudou antes da publicação.")
            if sha256(item["composed_path"]) != proof["composed_sha256"]:
                raise ValueError("Composição Artístico mudou antes da publicação.")

    entries = [{"target": str(art_target), "staged": str(art_stage)},
               {"target": str(final_target), "staged": str(final_stage)},
               {"target": str(path.parent), "staged": str(special_stage)}]
    publish(manga, folder, entries, validate)
    return records
