"""Stage one-page reset while retaining previous runs and explicit invalidation."""
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil

from central_v2.backend.orchestration.textoff_special.artifacts import sha256

from .final_consolidated_manifest import read_manifest, write_manifest
from .special_page_restore_backup import prepare as prepare_backup


def prepare(context: dict, folder: Path, backup_target: Path, identity: str) -> None:
    proposal, page = context["proposal"], context["proposal"]["page"]
    prepare_backup(context, folder)
    final_stage = folder / "stages/final"
    shutil.copytree(context["final_path"].parent.parent, final_stage)
    shutil.copyfile(context["source"], final_stage / page)
    final = context["final"]
    final["history"].append({"page": page, "superseded": final["pages"][page],
        "superseded_at": datetime.now(timezone.utc).isoformat(),
        "reason": "page_restoration", "backup": str(backup_target.relative_to(context["manga"])),
        "invalidated_runs": context["invalidated_runs"]})
    final["pages"][page] = {"page": page, "artifact": page,
        "sha256": proposal["restored_sha256"], "origin": proposal["source_origin"],
        "treatment": None, "input_sha256": None, "restoration_id": identity}
    write_manifest(final_stage, final)
    read_manifest(final_stage / "json/final-manifest.json", context["manga"], proposal["chapter"])
    special_stage = folder / "stages/special"
    shutil.copytree(context["special_path"].parent, special_stage)
    special = context["special"]
    for rows in special["treatments"].values():
        for row in rows:
            if row.get("page") == page:
                row["status"] = "pending"
                row.pop("result", None)
                row.pop("error", None)
    special.setdefault("page_restoration_history", []).append({"id": identity,
        "page": page, "backup": str(backup_target.relative_to(context["manga"])),
        "previous_sha256": proposal["current_sha256"],
        "final_manifest_sha256": proposal["final_manifest_sha256"],
        "special_manifest_sha256": proposal["special_manifest_sha256"],
        "restored_sha256": proposal["restored_sha256"],
        "check_compatibility": proposal["check_compatibility"],
        "invalidated_runs": context["invalidated_runs"],
        "occurrences": context["affected"]})
    staged_manifest = special_stage / context["special_path"].name
    staged_manifest.write_text(json.dumps(special, indent=2, ensure_ascii=False) + "\n")
    context["staged_special_sha256"] = sha256(staged_manifest)
