"""Inspect and transactionally reset one page to its verified automatic input."""
from datetime import datetime, timezone
from hashlib import sha256 as hash_bytes
import json
from pathlib import Path
import shutil

from central_v2.backend.orchestration.textoff_special.artifacts import sha256

from .auto_cleaner_check_manifest import _validate_chapter, manifest_path as check_path
from .final_consolidated import final_manifest_path, read_final_page
from .final_consolidated_manifest import read_manifest, write_manifest
from .special_styled_recovery import _resolve_source
from .special_styled_transaction import begin, discard_staging, publish
from .special_treatments_manifest import SCHEMA, manifest_path as special_path
from .special_page_restore_backup import prepare as prepare_backup, verify as verify_backup

AUTOMATIC = {"AUTO_CLEANER", "AUTO_CLEANER_TRANSPARENCIA"}
SPECIAL = {"PINCEL_ARTISTICO", "PINCEL_DEGRADE", "PINCEL_SUAVE"}
BACKUPS = "SPECIAL_PAGE_RESTORE_BACKUPS"
PROPOSAL_FIELDS = ("chapter", "page", "current_sha256", "restored_sha256",
                   "final_manifest_sha256", "special_manifest_sha256", "check_sha256",
                   "source_manifest_sha256", "source_origin", "affected_occurrences")


def _context(manga: Path, provider: str, chapter: str, page: str) -> dict:
    manga = Path(manga).resolve()
    _validate_chapter(chapter)
    if (not isinstance(page, str) or Path(page).name != page or page in {"", ".", ".."}
            or provider != manga.parent.name):
        raise ValueError("Página ou obra inválida para restauração.")
    final_path = final_manifest_path(manga, chapter).resolve()
    if not final_path.is_relative_to(manga):
        raise ValueError("Consolidado Final fora da obra.")
    final_hash = sha256(final_path)
    final = read_manifest(final_path, manga, chapter)
    current = final["pages"].get(page)
    current_path = final_path.parent.parent / page
    if not isinstance(current, dict) or sha256(current_path) != current.get("sha256"):
        raise ValueError("Página atual sem SHA verificável no Consolidado Final.")
    chain = [item.get("superseded") for item in final.get("history", [])
             if isinstance(item, dict) and item.get("page") == page]
    chain.append(current)
    baseline = max((i for i, row in enumerate(chain)
                    if isinstance(row, dict) and row.get("origin") in AUTOMATIC), default=-1)
    if baseline < 0 or baseline == len(chain) - 1:
        raise ValueError("Não existe sequência especial posterior a uma entrada automática.")
    previous = chain[baseline]
    for row in chain[baseline + 1:]:
        if (not isinstance(row, dict) or row.get("origin") not in SPECIAL
                or row.get("input_origin") != previous.get("origin")
                or row.get("input_sha256") != previous.get("sha256")):
            raise ValueError("Linhagem dos tratamentos especiais não é verificável.")
        previous = row
    first = chain[baseline + 1]
    source, source_manifest, source_hash = _resolve_source(manga, chapter, page, first)
    if not Path(source).resolve().is_relative_to(manga) or not Path(source_manifest).resolve().is_relative_to(manga):
        raise ValueError("Entrada automática fora da obra.")
    if sha256(source) != chain[baseline]["sha256"]:
        raise ValueError("Entrada automática difere do histórico final.")
    special_pathname = special_path(manga, chapter).resolve()
    special_hash = sha256(special_pathname)
    special = json.loads(special_pathname.read_text(encoding="utf-8"))
    check = check_path(manga, chapter).resolve()
    check_hash = sha256(check)
    if (special.get("schema") != SCHEMA or special.get("version") != 1
            or special.get("provider") != provider or special.get("manga") != manga.name
            or special.get("chapter") != chapter
            or (special.get("source_check") or {}).get("sha256") != check_hash):
        raise ValueError("Manifesto Especial obsoleto ou incompatível com o Check.")
    affected = [{"treatment": name, "id": row.get("id")}
                for name, rows in (special.get("treatments") or {}).items()
                for row in rows if isinstance(row, dict) and row.get("page") == page]
    if not affected or any(not isinstance(item["id"], str) for item in affected):
        raise ValueError("Página sem ocorrências especiais identificáveis.")
    proposal = {"chapter": chapter, "page": page, "current_sha256": current["sha256"],
        "restored_sha256": sha256(source), "final_manifest_sha256": final_hash,
        "special_manifest_sha256": special_hash, "check_sha256": check_hash,
        "source_manifest_sha256": source_hash, "source_origin": chain[baseline]["origin"],
        "affected_occurrences": len(affected)}
    if sha256(final_path) != final_hash or sha256(special_pathname) != special_hash:
        raise ValueError("Manifesto mudou durante a inspeção da restauração.")
    return {"proposal": proposal, "manga": manga, "final": final, "final_path": final_path,
            "current_path": current_path, "special": special, "special_path": special_pathname,
            "source": source, "source_manifest": source_manifest, "affected": affected}


def inspect(manga: Path, provider: str, chapter: str, page: str) -> dict:
    """Return a read-only proposal; old Artístico outputs and masks are unnecessary."""
    proposal = _context(manga, provider, chapter, page)["proposal"]
    return {**proposal, "version": proposal_version(proposal)}


def proposal_version(proposal: dict) -> str:
    canonical = {key: proposal.get(key) for key in PROPOSAL_FIELDS}
    return hash_bytes(json.dumps(canonical, sort_keys=True).encode()).hexdigest()


def images(manga: Path, provider: str, chapter: str, page: str, proposal: dict,
           side: str) -> bytes:
    context = _context(manga, provider, chapter, page)
    _match(proposal, context["proposal"])
    path = context["current_path"] if side == "current" else context["source"] if side == "restored" else None
    if path is None:
        raise ValueError("Lado da prévia de restauração inválido.")
    content = path.read_bytes()
    if hash_bytes(content).hexdigest() != context["proposal"]["current_sha256" if side == "current" else "restored_sha256"]:
        raise ValueError("Imagem de prévia mudou durante a leitura.")
    return content


def _match(given: dict, actual: dict) -> None:
    if not isinstance(given, dict) or any(given.get(key) != actual[key] for key in PROPOSAL_FIELDS):
        raise ValueError("Prévia obsoleta: atualize antes de restaurar a página.")


def restore(manga: Path, provider: str, chapter: str, page: str,
            proposal: dict, *, confirmed: bool = False) -> dict:
    if confirmed is not True:
        raise ValueError("Confirmação explícita necessária para restaurar a página.")
    context = _context(manga, provider, chapter, page)
    _match(proposal, context["proposal"])
    identity, folder = begin(context["manga"], chapter)
    backup_target = context["manga"] / BACKUPS / chapter / identity
    if backup_target.exists():
        raise ValueError("Destino do backup de restauração já existe.")
    try:
        _prepare(context, folder, backup_target, identity)
        def validate():
            if backup_target.exists():
                raise ValueError("Destino do backup de restauração já existe.")
            latest = _context(manga, provider, chapter, page)
            _match(proposal, latest["proposal"])
            verify_backup(folder / "stages/backup", proposal, context["manga"])
            if (sha256(folder / "stages/final" / page) != proposal["restored_sha256"]
                    or sha256(folder / "stages/special" / context["special_path"].name)
                    != context["staged_special_sha256"]):
                raise ValueError("Artefato preparado para restauração mudou.")
        entries = [{"target": str(backup_target), "staged": str(folder / "stages/backup")},
                   {"target": str(context["final_path"].parent.parent),
                    "staged": str(folder / "stages/final")},
                   {"target": str(context["special_path"].parent),
                    "staged": str(folder / "stages/special")}]
        publish(context["manga"], folder, entries, validate)
        return {"chapter": chapter, "page": page, "status": "restored",
                "backup": str(backup_target.relative_to(context["manga"])),
                "restored_sha256": proposal["restored_sha256"],
                "affected_occurrences": proposal["affected_occurrences"]}
    finally:
        if folder.exists():
            discard_staging(folder)


def _prepare(context, folder, backup_target, identity):
    proposal, page = context["proposal"], context["proposal"]["page"]
    prepare_backup(context, folder)
    final_stage = folder / "stages/final"
    shutil.copytree(context["final_path"].parent.parent, final_stage)
    shutil.copyfile(context["source"], final_stage / page)
    final = context["final"]
    final["history"].append({"page": page, "superseded": final["pages"][page],
        "superseded_at": datetime.now(timezone.utc).isoformat(),
        "reason": "page_restoration", "backup": str(backup_target.relative_to(context["manga"]))})
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
        "occurrences": context["affected"]})
    staged_manifest = special_stage / context["special_path"].name
    staged_manifest.write_text(json.dumps(special, indent=2, ensure_ascii=False) + "\n")
    context["staged_special_sha256"] = sha256(staged_manifest)
