"""Publish one reviewed Laboratory PNG with recoverable final-page history."""
from datetime import datetime, timezone
from pathlib import Path
import shutil

from central_v2.backend.orchestration.textoff_special.artifacts import sha256
from central_v2.backend.state.manga_state import resolve_manga
from .final_consolidated import _payload, read_final_page
from .final_consolidated_manifest import read_manifest, write_manifest
from .laboratorio_final_candidate import candidate
from .laboratorio_final_review import FIELDS, inspect
from .special_styled_transaction import begin, discard_staging, publish
from .stages import stage_chapter

ORIGIN = "LABORATORIO"


def apply(payload: dict, output_root: Path) -> dict:
    if (not isinstance(payload, dict) or set(payload) != {*FIELDS, "version", "confirmed"}
            or payload.get("confirmed") is not True
            or not isinstance(payload.get("version"), str)):
        raise ValueError("Confirmação e versão da comparação são obrigatórias.")
    identity = {key: payload[key] for key in FIELDS}
    review = inspect(identity, output_root)
    if review["version"] != payload["version"]:
        raise ValueError("PROPOSTA_OBSOLETA: compare as imagens novamente.")
    if review["current_sha256"] == review["candidate_sha256"]:
        raise ValueError("O resultado escolhido já é a imagem final vigente.")
    manga = resolve_manga(output_root, review["provider"], review["manga"]).resolve()
    target = stage_chapter(manga, "CONSOLIDADO_FINAL", review["chapter"],
                           read_legacy=False).resolve()
    if not target.is_relative_to(manga) or not target.is_dir():
        raise ValueError("Destino do Consolidado Final inválido.")
    transaction_id, folder = begin(manga, review["chapter"])
    try:
        staged = folder / "stages/final"
        archive, snapshot = _prepare(manga, target, staged, review, output_root, transaction_id)

        def validate():
            current = inspect(identity, output_root)
            if current["version"] != review["version"]:
                raise ValueError("PROPOSTA_OBSOLETA: Consolidado Final mudou.")
            _verify(staged, manga, review, archive, snapshot)

        def validate_published():
            _verify(target, manga, review, archive, snapshot)

        publish(manga, folder, [{"target": str(target), "staged": str(staged)}],
                validate, validate_published)
        return {"status": "applied", "chapter": review["chapter"],
                "page": review["page"], "run_id": review["run_id"],
                "sha256": review["candidate_sha256"], "previous_sha256": review["current_sha256"],
                "transaction_id": transaction_id}
    finally:
        if folder.exists():
            discard_staging(folder)


def _prepare(manga, target, staged, review, output_root, transaction_id):
    shutil.copytree(target, staged, symlinks=True)
    manifest = staged / "json/final-manifest.json"
    previous = read_manifest(manifest, manga, review["chapter"])
    page = review["page"]
    old = previous["pages"][page]
    if old["sha256"] != review["current_sha256"]:
        raise ValueError("PROPOSTA_OBSOLETA: página final mudou.")
    archive = Path("history") / old["sha256"] / page
    if not (staged / archive).resolve().is_relative_to(staged.resolve()):
        raise ValueError("Destino do histórico fora do Consolidado Final.")
    _copy_verified(staged / page, staged / archive, old["sha256"])
    source = candidate(manga, review["chapter"], page, review["treatment"],
                       review["run_id"], output_root)
    if source["sha256"] != review["candidate_sha256"]:
        raise ValueError("PROPOSTA_OBSOLETA: resultado experimental mudou.")
    snapshot = Path("laboratorio") / review["run_id"] / page
    if not (staged / snapshot).resolve().is_relative_to(staged.resolve()):
        raise ValueError("Destino da procedência fora do Consolidado Final.")
    _copy_verified(source["path"], staged / snapshot, source["sha256"])
    _copy_verified(source["path"], staged / page, source["sha256"], replace=True)
    now = datetime.now(timezone.utc).isoformat()
    history = list(previous.get("history", []))
    history.append({"page": page, "superseded": old, "superseded_at": now,
                    "reason": "laboratorio_apply", "archived_artifact": archive.as_posix(),
                    "archived_sha256": old["sha256"], "transaction_id": transaction_id})
    pages = dict(previous["pages"])
    pages[page] = {"page": page, "artifact": page, "sha256": source["sha256"],
                   "origin": ORIGIN, "treatment": source["treatment"],
                   "run_id": source["run_id"], "source_artifact": source["artifact"],
                   "source_sha256": source["source_sha256"],
                   "laboratory_snapshot": snapshot.as_posix(),
                   "visual_review": "confirmed",
                   "applied_at": now, "transaction_id": transaction_id,
                   "review_version": review["version"]}
    write_manifest(staged, _payload(manga, review["chapter"], pages, history,
                                    previous["source_intermediate_manifest_sha256"]))
    _verify(staged, manga, review, archive, snapshot)
    return archive, snapshot


def _copy_verified(source: Path, target: Path, digest: str, *, replace=False):
    if sha256(source) != digest:
        raise ValueError("Artefato de origem mudou durante a publicação.")
    if target.is_file() and not replace:
        if sha256(target) != digest:
            raise ValueError("Arquivo histórico divergente.")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    if sha256(target) != digest:
        raise ValueError("Cópia da imagem divergente.")


def _verify(folder, manga, review, archive, snapshot):
    payload = read_manifest(folder / "json/final-manifest.json", manga, review["chapter"])
    page = review["page"]
    rows = [entry for entry in payload.get("history", []) if isinstance(entry, dict)
            and entry.get("transaction_id") == payload["pages"][page].get("transaction_id")]
    row = payload["pages"][page]
    if (row.get("origin") != ORIGIN or row.get("sha256") != review["candidate_sha256"]
            or row.get("visual_review") != "confirmed"
            or row.get("treatment") != review["treatment"]
            or row.get("source_artifact") != review["artifact"]
            or row.get("source_sha256") != review["source_sha256"]
            or row.get("review_version") != review["version"]
            or row.get("run_id") != review["run_id"]
            or row.get("laboratory_snapshot") != snapshot.as_posix()
            or len(rows) != 1 or rows[0].get("archived_artifact") != archive.as_posix()
            or sha256(folder / archive) != review["current_sha256"]
            or sha256(folder / snapshot) != review["candidate_sha256"]):
        raise ValueError("Publicação final sem histórico ou procedência verificável.")
