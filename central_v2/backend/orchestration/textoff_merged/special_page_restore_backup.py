"""Keep and verify a full final-chapter snapshot before page restoration."""
import json
from pathlib import Path
import shutil

from central_v2.backend.orchestration.textoff_special.artifacts import sha256

from .final_consolidated_manifest import read_manifest


def prepare(context: dict, folder: Path) -> None:
    proposal = context["proposal"]
    backup = folder / "stages/backup"
    backup.mkdir(parents=True)
    shutil.copytree(context["final_path"].parent.parent, backup / "consolidado_final")
    shutil.copyfile(context["special_path"], backup / "special-treatments-manifest.json")
    evidence = {"page": proposal["page"], "page_sha256": proposal["current_sha256"],
        "final_manifest_sha256": proposal["final_manifest_sha256"],
        "special_manifest_sha256": proposal["special_manifest_sha256"],
        "source_sha256": proposal["restored_sha256"], "source_origin": proposal["source_origin"]}
    (backup / "backup.json").write_text(json.dumps(evidence, indent=2) + "\n")
    verify(backup, proposal, context["manga"])


def verify(backup: Path, proposal: dict, manga: Path) -> None:
    final = backup / "consolidado_final"
    evidence = json.loads((backup / "backup.json").read_text(encoding="utf-8"))
    if (evidence.get("page_sha256") != proposal["current_sha256"]
            or evidence.get("final_manifest_sha256") != proposal["final_manifest_sha256"]
            or evidence.get("special_manifest_sha256") != proposal["special_manifest_sha256"]
            or evidence.get("source_sha256") != proposal["restored_sha256"]
            or evidence.get("source_origin") != proposal["source_origin"]
            or sha256(final / proposal["page"]) != proposal["current_sha256"]
            or sha256(final / "json/final-manifest.json") != proposal["final_manifest_sha256"]
            or sha256(backup / "special-treatments-manifest.json") != proposal["special_manifest_sha256"]):
        raise ValueError("Backup da página ou metadados não é verificável.")
    read_manifest(final / "json/final-manifest.json", manga, proposal["chapter"])
