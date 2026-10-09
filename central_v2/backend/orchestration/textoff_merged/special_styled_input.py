"""Resolve Check-approved Artístico ROIs and verified input artifacts."""
import json
from pathlib import Path

from central_v2.backend.orchestration.textoff_special.artifacts import sha256
from central_v2.backend.orchestration.textoff_special.inputs import validate_selections

from .auto_cleaner_check_manifest import _read_check_manifest, manifest_path as check_path
from .special_degrade_input import selected_input
from .special_treatments_manifest import SCHEMA, manifest_path as special_path
from .special_styled_output import MANIFEST as ART_MANIFEST, SCHEMA as ART_SCHEMA, STAGE as ART_STAGE
from .artifact_paths import artifact_ref
from .stages import stage_chapter
from .special_styled_transaction import transaction_lock
from .special_page_restore_check import require_restored_compatibility


def pending_pages(manga: Path, provider: str, chapter: str, *, retry=False,
                  payload_override=None, selections=None):
    manga = Path(manga).resolve()
    with transaction_lock(manga):
        return _pending_pages(manga, provider, chapter, retry=retry,
                              payload_override=payload_override, selections=selections)


def _pending_pages(manga, provider, chapter, *, retry=False, payload_override=None,
                   selections=None):
    manga = Path(manga).resolve()
    path = special_path(manga, chapter)
    digest = sha256(path)
    payload = payload_override or json.loads(path.read_text(encoding="utf-8"))
    if (payload.get("schema") != SCHEMA or payload.get("version") != 1
            or payload.get("provider") != provider or payload.get("manga") != manga.name
            or payload.get("chapter") != chapter):
        raise ValueError("Manifesto Especial incompatível com a obra selecionada.")
    check_manifest = payload.get("source_check") or {}
    check = check_path(manga, chapter)
    if (check_manifest.get("path") != str(check.relative_to(manga))
            or check_manifest.get("sha256") != sha256(check)):
        raise ValueError("Manifesto Especial obsoleto em relação ao Check.")
    approved = _read_check_manifest(check, {
        "provider": provider, "obra": manga.name, "capitulo": chapter,
    })["approved_occurrences"]
    decisions = {(row.get("page"), row.get("id")): row for row in approved}
    rows = (payload.get("treatments") or {}).get("estilizado")
    if not isinstance(rows, list):
        raise ValueError("Tratamento Artístico ausente do Manifesto Especial.")
    groups, seen = {}, set()
    if selections is not None and (not isinstance(selections, set) or not selections):
        raise ValueError("Selecione ocorrências Artístico válidas.")
    allowed = {"pending", "failed"} if retry else {"pending"}
    for row in rows:
        if (not isinstance(row, dict) or row.get("treatment") != "estilizado"
                or row.get("tipo") != "balao_estilizado"):
            raise ValueError("Ocorrência incompatível com Artístico.")
        decision = decisions.get((row.get("page"), row.get("id")))
        if (decision is None or decision.get("tipo") != row["tipo"]
                or decision.get("box_pixels") != row.get("box_pixels")):
            raise ValueError("Ocorrência Artístico diverge da decisão aprovada do Check.")
        if row.get("status") not in allowed:
            continue
        page, identity = row.get("page"), row.get("id")
        if (not isinstance(page, str) or not page or Path(page).name != page
                or not isinstance(identity, str) or not identity or (page, identity) in seen):
            raise ValueError("Página ou identidade inválida no Manifesto Especial.")
        seen.add((page, identity))
        validate_selections([row.get("box_pixels")])
        if selections is None or (page, identity) in selections:
            groups.setdefault(page, []).append(row)
    if selections is not None and selections - seen:
        raise ValueError("Ocorrência Artístico não elegível ou desatualizada.")
    completed_pages = {row["page"] for row in rows
                       if row.get("status") in {"processed", "no_change"}}
    if payload_override is None and set(groups) & completed_pages:
        raise ValueError("A página já contém Artístico processado; autoria incremental indisponível.")
    for page in groups:
        require_restored_compatibility(manga, provider, chapter, page)
    if sha256(path) != digest:
        raise ValueError("Manifesto Especial mudou durante a leitura.")
    if not groups:
        raise ValueError(f"Capítulo {chapter} não possui Artístico elegível.")
    return path, digest, payload, groups


def historical_input(manga: Path, chapter: str, page: str) -> dict:
    """Resolve the immutable detection input and prior output for one page."""
    manga = Path(manga).resolve()
    with transaction_lock(manga):
        return _historical_input(manga, chapter, page)


def _historical_input(manga, chapter, page):
    folder = stage_chapter(manga, ART_STAGE, chapter, read_legacy=False).resolve()
    manifest = (folder / artifact_ref("json", ART_MANIFEST)).resolve()
    if Path(page).name != page:
        raise ValueError("Página histórica Artístico inválida.")
    if not manifest.is_file():
        from .special_styled_recovery import recover_from_final_history
        return recover_from_final_history(manga, chapter, page)
    if not manifest.is_relative_to(folder):
        raise ValueError("Manifesto ou página histórica Artístico ausente.")
    manifest_hash = sha256(manifest)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    if (payload.get("schema") != ART_SCHEMA or payload.get("version") != 1
            or payload.get("manga") != manga.name or payload.get("chapter") != chapter
            or payload.get("treatment") != "estilizado"):
        raise ValueError("Manifesto histórico Artístico incompatível.")
    record, archived = _historical_record(payload, page)
    source = record.get("input") or {}
    snapshot = _artifact(folder, (record.get("input_artifact") or {}).get("artifact"), "input")
    source_hash = source.get("sha256")
    if (not isinstance(source_hash, str) or source_hash != (record.get("input_artifact") or {}).get("sha256")
            or sha256(snapshot) != source_hash):
        raise ValueError("Snapshot histórico Artístico ausente ou com hash divergente.")
    output_info = record.get("output") or {}
    output_ref = output_info.get("artifact")
    output = _archive_output(folder, archived, output_ref, output_info.get("sha256"))
    if sha256(manifest) != manifest_hash:
        raise ValueError("Manifesto Artístico mudou durante a leitura do snapshot.")
    source_manifest = record.get("consolidated_manifest") or {}
    if not isinstance(source_manifest.get("path"), str) or not isinstance(source_manifest.get("sha256"), str):
        raise ValueError("Manifesto da entrada histórica Artístico ausente.")
    return {"path": str(snapshot), "sha256": source_hash, "filename": page, "page": page,
            "selected_from": record.get("selected_from"), "level": "ARTISTICO_HISTORICAL_INPUT",
            "art_manifest": str(manifest), "art_manifest_sha256": manifest_hash,
            "chapter": chapter, "manga": str(manga),
            "predecessors": [{"path": str(manifest), "sha256": manifest_hash}],
            "consolidated_manifest": (record.get("consolidated_manifest") or {}).get("path"),
            "consolidated_manifest_sha256": (record.get("consolidated_manifest") or {}).get("sha256"),
            "prior_output": str(output), "prior_output_sha256": output_info["sha256"],
            "prior_run_id": record.get("run_id"),
            "proofs": [{"path": str(manifest), "sha256": manifest_hash},
                       source_manifest]}


def _historical_record(payload, page):
    current = (payload.get("pages") or {}).get(page)
    if isinstance(current, dict):
        return current, None
    for run in reversed(payload.get("superseded_results", [])):
        for item in run.get("pages", []):
            record = item.get("record") or {}
            if item.get("page") == page or record.get("page") == page:
                return record, item.get("archived_artifacts", [])
    raise ValueError("Snapshot histórico Artístico não está registrado.")


def _artifact(folder, reference, section):
    relative = Path(reference) if isinstance(reference, str) else Path()
    path = (folder / relative).resolve()
    if (not isinstance(reference, str) or relative.is_absolute() or ".." in relative.parts
            or not path.is_relative_to(folder / section) or not path.is_file()):
        raise ValueError(f"Artefato {section} Artístico inválido.")
    return path


def _archive_output(folder, archived, reference, expected):
    try:
        path = _artifact(folder, reference, "clean")
    except ValueError:
        path = None
    if path and sha256(path) == expected:
        return path
    for item in archived or []:
        artifact = item.get("artifact")
        candidate = (folder / artifact).resolve() if isinstance(artifact, str) else folder
        if (candidate.is_relative_to(folder / "archive") and candidate.is_file()
                and item.get("sha256") == expected and sha256(candidate) == expected):
            return candidate
    raise ValueError("Resultado Artístico anterior ausente ou com hash divergente.")


def validate_chapters(manga: Path, provider: str, chapters: object, *, retry=False,
                      selections=None):
    if (not isinstance(chapters, list) or not chapters
            or any(not isinstance(name, str) or not name or Path(name).name != name
                   or name in {".", ".."} or "\\" in name for name in chapters)
            or len(set(chapters)) != len(chapters)):
        raise ValueError("Selecione capítulos válidos sem repetição.")
    if selections is not None and (not isinstance(selections, dict)
                                   or set(selections) != set(chapters)):
        raise ValueError("Seleção Artístico incompleta para os capítulos solicitados.")
    for chapter in chapters:
        pending_pages(manga, provider, chapter, retry=retry,
                      selections=selections.get(chapter) if selections is not None else None)
    return chapters


__all__ = ["pending_pages", "selected_input", "validate_chapters"]
