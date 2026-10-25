"""Retain a verified authorization mask for downstream dependency checks."""
from pathlib import Path
import shutil

from central_v2.backend.orchestration.textoff_special.artifacts import contained_file, sha256
from central_v2.backend.orchestration.textoff_special.catalog import STAGING_ROOT
from central_v2.backend.orchestration.textoff_special.run_paths import run_from_manifest


def persist_write_mask(staged: Path, run: dict, page: str) -> dict | None:
    name = ((run.get("treatment") or {}).get("artifacts") or {}).get("authorized_mask")
    if not name:
        return None
    reference = f"treatment/{name}"
    folder = run_from_manifest(run, "textoff_especiais_v2", legacy=STAGING_ROOT)
    source = contained_file(folder, reference)
    expected = (run.get("artifacts") or {}).get(reference)
    if not isinstance(expected, str) or sha256(source) != expected:
        raise ValueError("Máscara autorizada do tratamento posterior divergente.")
    relative = f"authorship/{run['run_id']}/{Path(page).stem}-write.png"
    target = staged / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    if sha256(target) != expected:
        raise ValueError("Máscara de autoria posterior persistida divergente.")
    return {"artifact": relative, "sha256": expected}
