"""Authenticate a pre-special page from its first treatment's saved input."""
import json
from pathlib import Path

from central_v2.backend.orchestration.textoff_special.artifacts import sha256
from central_v2.backend.orchestration.textoff_special.catalog import treatment_for

from .special_styled_recovery import _resolve_source
from .stages import stage_root

STAGES = {
    "PINCEL_ARTISTICO": ("PINCEL_ARTISTICO", "artistico-manifest.json", "estilizado"),
    "PINCEL_DEGRADE": ("PINCEL_DEGRADE", "degrade-manifest.json", "degrade"),
    "PINCEL_SUAVE": ("PINCEL_SUAVE", "suave-manifest.json", "gradiente_suave"),
}


def restoration_source(manga: Path, chapter: str, page: str, first: dict) -> tuple[Path, Path, str]:
    """Prefer the stage source; fall back to a fully linked immutable input snapshot."""
    try:
        return _resolve_source(manga, chapter, page, first)
    except ValueError:
        return _snapshot(manga, chapter, page, first)


def _snapshot(manga: Path, chapter: str, page: str, first: dict):
    if (first.get("origin") not in STAGES or first.get("page") != page
            or first.get("artifact") != page or Path(page).name != page):
        raise ValueError("Tratamento inicial não identifica a página histórica.")
    stage, filename, treatment = STAGES[first["origin"]]
    run_id = first.get("run_id")
    if not isinstance(run_id, str) or not run_id.isalnum():
        raise ValueError("Run histórico sem identidade verificável.")
    folder = (stage_root(manga, stage, read_legacy=False) / chapter).resolve()
    manifest = (folder / "json" / filename).resolve()
    if (not folder.is_relative_to(Path(manga).resolve()) or not manifest.is_relative_to(folder)
            or not manifest.is_file()):
        raise ValueError("Manifesto do primeiro tratamento especial ausente.")
    manifest_hash = sha256(manifest)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    if (payload.get("schema") != f"textoff_pincel_{stage.removeprefix('PINCEL_').lower()}_manifest_v1"
            or payload.get("version") != 1 or payload.get("provider") != manga.parent.name
            or payload.get("manga") != manga.name or payload.get("chapter") != chapter
            or payload.get("treatment") != treatment
            or payload.get("algorithm") != treatment_for(treatment).algorithm):
        raise ValueError("Manifesto do tratamento histórico incompatível.")
    matches = []
    current = (payload.get("pages") or {}).get(page)
    if isinstance(current, dict):
        matches.append((current, []))
    for group in payload.get("superseded_results", []):
        for item in group.get("pages", []):
            if isinstance(item, dict) and item.get("page") == page:
                matches.append((item.get("record"), item.get("archived_artifacts") or []))
    selected = [(row, archived) for row, archived in matches
                if isinstance(row, dict) and row.get("run_id") == run_id]
    if len(selected) != 1:
        raise ValueError("Run inicial ausente ou ambíguo no manifesto histórico.")
    row, archived = selected[0]
    source = row.get("input") or {}
    saved = row.get("input_artifact") or {}
    source_manifest = row.get("consolidated_manifest") or {}
    output = row.get("output") or {}
    expected_ref = f"input/{run_id}/{page}"
    if (row.get("provider") != manga.parent.name or row.get("manga") != manga.name
            or row.get("chapter") != chapter or row.get("page") != page
            or row.get("treatment") != treatment or row.get("selected_from") != first.get("input_origin")
            or source.get("sha256") != first.get("input_sha256")
            or saved.get("sha256") != first.get("input_sha256")
            or saved.get("artifact") != expected_ref
            or source_manifest.get("sha256") != first.get("input_manifest_sha256")
            or output.get("sha256") != first.get("sha256")):
        raise ValueError("Snapshot não corresponde à linhagem do Consolidado Final.")
    snapshot = (folder / expected_ref).resolve()
    if (not snapshot.is_relative_to(folder / "input") or not snapshot.is_file()
            or sha256(snapshot) != first["input_sha256"]):
        raise ValueError("Snapshot histórico ausente ou com SHA divergente.")
    _verify_output(folder, output, archived, first["sha256"])
    if sha256(manifest) != manifest_hash:
        raise ValueError("Manifesto histórico mudou durante a inspeção.")
    return snapshot, manifest, manifest_hash


def _verify_output(folder: Path, output: dict, archived: list, digest: str) -> None:
    references = [output]
    references.extend(item for item in archived if isinstance(item, dict))
    for item in references:
        ref = item.get("artifact")
        if not isinstance(ref, str) or Path(ref).is_absolute() or ".." in Path(ref).parts:
            continue
        candidate = (folder / ref).resolve()
        if (candidate.is_relative_to(folder / "clean")
                or candidate.is_relative_to(folder / "archive")) and candidate.is_file():
            if item.get("sha256") == digest and sha256(candidate) == digest:
                return
    raise ValueError("Saída do primeiro tratamento histórico sem SHA verificável.")
