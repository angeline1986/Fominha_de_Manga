"""Restore a verified historical final PNG through the publication journal."""
from datetime import datetime, timezone
from pathlib import Path
import shutil

from central_v2.backend.orchestration.textoff_special.artifacts import sha256
from central_v2.backend.state.manga_state import resolve_manga
from .final_consolidated import _payload
from .final_consolidated_manifest import read_manifest, write_manifest
from .laboratorio_final_apply import _copy_verified
from .laboratorio_final_candidate import image_size
from .laboratorio_final_history import FIELDS, archived_path, revision_entry
from .special_styled_transaction import begin, discard_staging, publish
from .stages import stage_chapter


def restore(payload: dict, output_root: Path) -> dict:
    if (not isinstance(payload, dict) or set(payload) != {*FIELDS, "version", "revision_id", "confirmed"}
            or payload.get("confirmed") is not True
            or any(not isinstance(payload.get(key), str) or not payload[key]
                   for key in ("version", "revision_id"))):
        raise ValueError("Confirmação e versão histórica são obrigatórias.")
    identity = {key: payload[key] for key in FIELDS}
    history, entry, source = revision_entry(identity, output_root, payload["version"],
                                            payload["revision_id"])
    old = entry["superseded"]
    if old["sha256"] == history["current"]["sha256"]:
        raise ValueError("Esta imagem já é a versão final vigente.")
    manga = resolve_manga(output_root, identity["provider"], identity["manga"]).resolve()
    target = stage_chapter(manga, "CONSOLIDADO_FINAL", identity["chapter"],
                           read_legacy=False).resolve()
    if not target.is_relative_to(manga) or not target.is_dir():
        raise ValueError("Destino do Consolidado Final inválido.")
    transaction_id, folder = begin(manga, identity["chapter"])
    try:
        staged = folder / "stages/final"
        archive = _prepare(manga, target, staged, source, old, history,
                           payload["revision_id"], transaction_id)

        def validate():
            current, selected, _path = revision_entry(identity, output_root,
                payload["version"], payload["revision_id"])
            if (current["version"] != history["version"]
                    or selected.get("archived_sha256") != old["sha256"]):
                raise ValueError("PROPOSTA_OBSOLETA: histórico mudou.")
            _verify(staged, manga, history, old, archive, transaction_id)

        def validate_published():
            _verify(target, manga, history, old, archive, transaction_id)

        publish(manga, folder, [{"target": str(target), "staged": str(staged)}],
                validate, validate_published)
        return {"status": "restored", "chapter": identity["chapter"], "page": identity["page"],
                "sha256": old["sha256"], "previous_sha256": history["current"]["sha256"],
                "transaction_id": transaction_id}
    finally:
        if folder.exists():
            discard_staging(folder)


def _prepare(manga, target, staged, source, old, history, revision_id, transaction_id):
    shutil.copytree(target, staged, symlinks=True)
    chapter, page = history["chapter"], history["page"]
    previous = read_manifest(staged / "json/final-manifest.json", manga, chapter)
    current = previous["pages"][page]
    if current["sha256"] != history["current"]["sha256"]:
        raise ValueError("PROPOSTA_OBSOLETA: página final mudou.")
    if image_size(source) != image_size(staged / page):
        raise ValueError("Dimensões diferentes da página no Consolidado Final.")
    archive = Path("history") / current["sha256"] / page
    destination = (staged / archive).resolve()
    if not destination.is_relative_to(staged.resolve()):
        raise ValueError("Destino do histórico fora do Consolidado Final.")
    _copy_verified(staged / page, destination, current["sha256"])
    _copy_verified(source, staged / page, old["sha256"], replace=True)
    now = datetime.now(timezone.utc).isoformat()
    timeline = list(previous.get("history", []))
    timeline.append({"page": page, "superseded": current, "superseded_at": now,
                     "reason": "laboratorio_restore", "archived_artifact": archive.as_posix(),
                     "archived_sha256": current["sha256"], "transaction_id": transaction_id,
                     "restored_revision_id": revision_id})
    pages = dict(previous["pages"])
    pages[page] = {**old, "restored_at": now, "restoration_id": transaction_id,
                   "restored_revision_id": revision_id}
    write_manifest(staged, _payload(manga, chapter, pages, timeline,
                                    previous["source_intermediate_manifest_sha256"]))
    _verify(staged, manga, history, old, archive, transaction_id)
    return archive


def _verify(folder, manga, history, old, archive, transaction_id):
    manifest = read_manifest(folder / "json/final-manifest.json", manga, history["chapter"])
    page = history["page"]
    row = manifest["pages"][page]
    events = [item for item in manifest.get("history", []) if isinstance(item, dict)
              and item.get("transaction_id") == transaction_id]
    if (row.get("sha256") != old["sha256"] or row.get("origin") != old.get("origin")
            or row.get("restoration_id") != transaction_id or len(events) != 1
            or events[0].get("reason") != "laboratorio_restore"
            or events[0].get("archived_artifact") != archive.as_posix()
            or sha256(folder / archive) != history["current"]["sha256"]
            or not archived_path(folder, events[0], page)):
        raise ValueError("Restauração sem histórico verificável.")
