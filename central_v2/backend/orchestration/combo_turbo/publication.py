"""Publish validated Combo results to disposable consolidated copies."""
from pathlib import Path
import uuid

from central_v2.backend.orchestration.textoff_special.artifacts import sha256
from central_v2.backend.orchestration.textoff_merged.consolidated import consolidated_is_current
from central_v2.backend.orchestration.textoff_merged.final_consolidated import (
    MANIFEST as FINAL_MANIFEST,
)
from central_v2.backend.orchestration.textoff_merged.final_consolidated_manifest import read_manifest
from central_v2.backend.orchestration.textoff_merged.special_styled_transaction import (
    begin, discard_staging, publish as publish_directories,
)
from central_v2.backend.orchestration.textoff_merged.stages import CONSOLIDATED, stage_chapter
from .publication_candidates import prepare_candidates
from .publication_manifest import (MANIFEST, path_for, prepare_generation,
                                   read_manifest as read_combo_manifest)
from .publication_validation import validate_run


def publish_combo(manga, run_root, chapter, run_result, *, run_id=None, phase_hook=None):
    """Atomically publish Combo, logical, and final stages inside its snapshot."""
    manga, run_root = Path(manga).resolve(), Path(run_root).resolve()
    preflight = validate_run(manga, run_root, chapter, run_result)
    identity = run_id or run_result.get("run_id") or uuid.uuid4().hex
    if run_result.get("run_id") != identity:
        raise ValueError("run_id solicitado diverge do resultado Combo.")
    composed = sum(row.get("status") == "COMPOSED" for row in preflight["pages"].values())
    if not composed:
        states = {row.get("status") for row in preflight["pages"].values()}
        status = "NO_WORK" if states == {"NO_WORK"} else (
            "BLOCKED" if states and states.issubset({"BLOCKED", "CONFLICT"}) else "PARTIAL")
        return {"status": status, "run_id": identity, "published": 0,
                "total": len(preflight["pages"]), "counts": _state_counts(preflight["pages"]),
                "blocked": _blocked(preflight["pages"]), "reasons": ["NO_COMPOSED_PAGES"]}
    target_combo = path_for(manga, chapter)
    if target_combo.exists():
        current = read_combo_manifest(manga, chapter)
        if current.get("run_id") == identity:
            _require_same_run(current.get("run_pages", {}), preflight["pages"])
            return {"status": "ALREADY_PUBLISHED", "run_id": identity,
                    "published": sum(row.get("status") == "COMPOSED" for row in current["pages"].values()),
                    "blocked": current.get("blocked_count", 0)}
    transaction, folder = begin(manga, chapter)
    try:
        staged_combo = folder / "stages" / "combo"
        staged_logical = folder / "stages" / "logical"
        staged_final = folder / "stages" / "final"
        previous = read_combo_manifest(manga, chapter) if target_combo.exists() else None
        combo_manifest, _generation = prepare_generation(
            manga, chapter, staged_combo, preflight["pages"], run_id=identity, previous=previous)
        combo_manifest_hash = sha256(staged_combo / "json" / MANIFEST)
        combo_manifest["_candidate_sha256"] = combo_manifest_hash
        logical_payload = prepare_candidates(manga, chapter, staged_combo, combo_manifest,
                                             staged_logical, staged_final)
        if callable(phase_hook):
            phase_hook("CANDIDATES_PREPARED")
        entries = [{"target": str(path_for(manga, chapter)), "staged": str(staged_combo)},
            {"target": str(stage_chapter(manga, CONSOLIDATED, chapter, read_legacy=False)),
             "staged": str(staged_logical)},
            {"target": str(stage_chapter(manga, "CONSOLIDADO_FINAL", chapter,
                                          read_legacy=False)), "staged": str(staged_final)}]
        _validate_candidate(staged_combo, staged_logical, staged_final, manga, chapter,
                            combo_manifest_hash, logical_payload)
        def validate_before_publish():
            fresh = validate_run(manga, run_root, chapter, run_result)
            if (fresh["logical_hash"] != preflight["logical_hash"]
                    or fresh["final_hash"] != preflight["final_hash"]):
                raise ValueError("Revisão de consolidado mudou durante a preparação.")
            _validate_candidate(staged_combo, staged_logical, staged_final, manga, chapter,
                                combo_manifest_hash, logical_payload)
        publish_directories(manga, folder, entries, validate_before_publish,
            validate_published=lambda: _verify_published(manga, chapter, combo_manifest_hash))
        partial = (_blocked(preflight["pages"]) > 0 or bool(run_result.get("errors"))
                   or any(row.get("status") == "PARTIAL" for row in run_result["results"]))
        status = "PARTIAL" if partial else "COMPLETED"
        return {"status": status, "run_id": identity, "published": composed,
                "total": len(preflight["pages"]), "counts": _state_counts(preflight["pages"]),
                "blocked": _blocked(preflight["pages"]), "transaction_id": transaction,
                "combo_manifest_sha256": combo_manifest_hash,
                "logical_manifest_sha256": sha256(stage_chapter(
                    manga, CONSOLIDATED, chapter, read_legacy=False) / "json/clean-manifest.json"),
                "final_manifest_sha256": sha256(stage_chapter(
                    manga, "CONSOLIDADO_FINAL", chapter, read_legacy=False) / "json" / FINAL_MANIFEST)}
    except BaseException:
        discard_staging(folder)
        raise


def _validate_candidate(combo, logical, final, manga, chapter, combo_hash, logical_payload):
    combo_manifest = read_combo_manifest(manga, chapter, combo)
    logical_path = logical / "json" / "clean-manifest.json"
    final_path = final / "json" / FINAL_MANIFEST
    if (sha256(combo / "json" / MANIFEST) != combo_hash
            or combo_manifest.get("chapter") != chapter
            or not logical_path.is_file() or not final_path.is_file()
            or logical_payload.get("source_combo_manifest_sha256") != combo_hash):
        raise ValueError("Manifestos candidatos não formam uma revisão coerente.")
    payload = __import__("json").loads(logical_path.read_text(encoding="utf-8"))
    if payload != logical_payload:
        raise ValueError("Manifesto lógico candidato divergiu.")
    from central_v2.backend.orchestration.textoff_merged.final_consolidated_manifest import read_manifest
    final_manifest = read_manifest(final_path, manga, chapter)
    if final_manifest.get("source_intermediate_manifest_sha256") != sha256(logical_path):
        raise ValueError("Consolidado Final não referencia o candidato lógico.")


def _verify_published(manga, chapter, combo_hash):
    combo = read_combo_manifest(manga, chapter)
    logical = stage_chapter(manga, CONSOLIDATED, chapter, read_legacy=False) / "json/clean-manifest.json"
    final = stage_chapter(manga, "CONSOLIDADO_FINAL", chapter, read_legacy=False) / "json" / FINAL_MANIFEST
    if (sha256(path_for(manga, chapter) / "json" / MANIFEST) != combo_hash
            or not consolidated_is_current(manga, chapter)):
        raise ValueError("Consolidado lógico publicado falhou na verificação final.")
    final_data = read_manifest(final, manga, chapter)
    if final_data.get("source_intermediate_manifest_sha256") != sha256(logical):
        raise ValueError("Consolidado Final publicado aponta para outra revisão.")


def _require_same_run(published, candidate):
    if set(published) != set(candidate):
        raise ValueError("run_id já publicado com conjunto de páginas diferente.")
    fields = ("status", "sha256", "report_sha256", "check_manifest_sha256",
              "level1_manifest_sha256", "source_solids_sha256", "source_glass_sha256",
              "mask_sha256")
    for page, row in candidate.items():
        old = published[page]
        same = all(old.get(key) == row.get(key) for key in fields if key != "sha256")
        same = same and old.get("sha256") == row.get("sha256", row.get("result_sha256"))
        if not same:
            raise ValueError(f"run_id já publicado com proveniência divergente: {page}.")


def _blocked(pages):
    return sum(row.get("status") in {"CONFLICT", "BLOCKED", "FAILED", "INVALID"}
               for row in pages.values())


def _state_counts(pages):
    counts = {state: 0 for state in ("COMPOSED", "NO_WORK", "CONFLICT", "BLOCKED", "FAILED", "INVALID")}
    for row in pages.values():
        state = row.get("status")
        counts[state if state in counts else "FAILED"] += 1
    return counts
