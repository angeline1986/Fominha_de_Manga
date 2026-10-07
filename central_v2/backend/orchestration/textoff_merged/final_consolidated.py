"""Manage the independent, page-complete TextOff final image set."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import tempfile

from central_v2.backend.orchestration.textoff_special.artifacts import sha256

from .artifact_paths import artifact_ref, prepare_artifact_dirs
from .consolidated import consolidated_is_current
from .consolidated_artifacts import consolidated_image
from .final_consolidated_manifest import read_manifest, write_manifest
from .level2_validation import promote_stage
from .stages import LEVEL1, LEVEL2, stage_chapter

STAGE = "CONSOLIDADO_FINAL"
SCHEMA = "textoff_consolidado_final_manifest_v1"
MANIFEST = "final-manifest.json"
PINCEL_STAGES = {"degrade": ("PINCEL_DEGRADE", "PINCEL_DEGRADE"),
                 "gradiente_suave": ("PINCEL_SUAVE", "PINCEL_SUAVE")}
AUTOMATIC_ORIGINS = {LEVEL1: "AUTO_CLEANER", LEVEL2: "AUTO_CLEANER_TRANSPARENCIA"}
TREATMENT_ORIGINS = {"degrade": "PINCEL_DEGRADE", "gradiente_suave": "PINCEL_SUAVE"}


def final_manifest_path(manga: Path, chapter: str) -> Path:
    return stage_chapter(manga, STAGE, chapter, read_legacy=False) / "json" / MANIFEST


def read_final_page(manga: Path, chapter: str, page: str) -> tuple[dict, Path, str]:
    folder = stage_chapter(manga, STAGE, chapter, read_legacy=False).resolve()
    manifest_path = final_manifest_path(manga, chapter).resolve()
    if not manifest_path.is_relative_to(folder) or not manifest_path.is_file():
        raise ValueError("Consolidado Final indisponível.")
    digest = sha256(manifest_path)
    payload = read_manifest(manifest_path, manga, chapter)
    row = payload["pages"].get(page)
    if not isinstance(row, dict) or row.get("artifact") != page or Path(page).name != page:
        raise ValueError("Página ausente no Consolidado Final.")
    image = (folder / page).resolve()
    if (not image.is_relative_to(folder) or not image.is_file()
            or sha256(image) != row.get("sha256") or sha256(manifest_path) != digest):
        raise ValueError("Imagem ou hash divergente no Consolidado Final.")
    return row, image, digest


def resolve_final_input(manga: Path, chapter: str, page: str, expected_hash: str) -> dict:
    _row, image, manifest_hash = read_final_page(manga, chapter, page)
    digest = sha256(image)
    if digest != expected_hash:
        raise ValueError("PROPOSTA_OBSOLETA: a versão vigente mudou.")
    manifest = final_manifest_path(manga, chapter).resolve()
    return {"path": str(image), "sha256": digest, "level": "CONSOLIDADO_FINAL",
            "chapter": chapter, "filename": page, "manga": str(Path(manga).resolve()),
            "predecessors": [{"path": str(manifest), "sha256": manifest_hash}]}


def rebuild_final_baseline(manga: Path, chapter: str) -> dict:
    if not consolidated_is_current(manga, chapter):
        raise ValueError(f"Consolidado intermediário inválido para Cap. {chapter}.")
    intermediate = stage_chapter(manga, "TO_MERGED_CONSOLIDADO", chapter)
    intermediate_manifest_path = intermediate / "json/clean-manifest.json"
    intermediate_hash = sha256(intermediate_manifest_path)
    intermediate_manifest = json.loads(intermediate_manifest_path.read_text(encoding="utf-8"))
    selections = intermediate_manifest.get("selections")
    if not isinstance(selections, list) or not selections:
        raise ValueError("Consolidado intermediário sem páginas.")
    target = stage_chapter(manga, STAGE, chapter, read_legacy=False).resolve()
    if not target.is_relative_to(Path(manga).resolve()):
        raise ValueError("Destino do Consolidado Final fora da obra.")
    previous = _load_existing(target, manga, chapter)
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".final-consolidated-", dir=target.parent) as work:
        staged = Path(work) / "stage"
        if target.is_dir():
            shutil.copytree(target, staged)
        else:
            staged.mkdir()
            prepare_artifact_dirs(staged)
        old_pages = previous.get("pages", {}) if previous else {}
        pages, history = {}, list(previous.get("history", [])) if previous else []
        for item in selections:
            page, source_stage = item.get("source"), item.get("selected_from")
            if (not isinstance(page, str) or Path(page).name != page
                    or source_stage not in AUTOMATIC_ORIGINS):
                raise ValueError("Seleção automática inválida para o Consolidado Final.")
            old = old_pages.get(page)
            if old and old.get("origin") in set(TREATMENT_ORIGINS.values()):
                pages[page] = old
                continue
            image = consolidated_image(manga, chapter, Path(item["artifact"]).name)
            if image is None or sha256(image) != item.get("sha256"):
                raise ValueError(f"Imagem automática inválida para {page}.")
            destination = staged / page
            shutil.copyfile(image, destination)
            digest = sha256(destination)
            if digest != item["sha256"]:
                raise ValueError(f"Cópia final divergente para {page}.")
            pages[page] = {"page": page, "artifact": page, "sha256": digest,
                           "origin": AUTOMATIC_ORIGINS[source_stage], "treatment": None,
                           "input_sha256": None}
            if old:
                history.append({"page": page, "superseded": old,
                                "superseded_at": datetime.now(timezone.utc).isoformat()})
        if len(pages) != len(selections):
            raise ValueError("Consolidado Final não contém uma versão por página.")
        payload = _payload(manga, chapter, pages, history, intermediate_hash)
        write_manifest(staged, payload)
        if sha256(intermediate_manifest_path) != intermediate_hash:
            raise ValueError("Consolidado intermediário mudou durante a montagem final.")
        promote_stage(staged, target)
    return {"chapter": chapter, "pages": len(pages), "manifest": str(final_manifest_path(manga, chapter))}


def promote_treatment_pages(manga: Path, chapter: str, treatment: str,
                            records: dict, page_runs: list[dict]) -> dict:
    if treatment not in PINCEL_STAGES:
        raise ValueError("Tratamento sem promoção para o Consolidado Final.")
    target = stage_chapter(manga, STAGE, chapter, read_legacy=False).resolve()
    previous = _load_existing(target, manga, chapter)
    if not previous or not target.is_dir():
        raise ValueError("Consolidado Final ainda não foi montado.")
    target_manifest = final_manifest_path(manga, chapter)
    target_hash = sha256(target_manifest)
    target.parent.mkdir(parents=True, exist_ok=True)
    promoted = 0
    with tempfile.TemporaryDirectory(prefix=".final-promotion-", dir=target.parent) as work:
        staged = Path(work) / "stage"
        shutil.copytree(target, staged)
        pages, history = dict(previous["pages"]), list(previous.get("history", []))
        for item in page_runs:
            source = item["source"]
            page = source["page"]
            record = records.get(page)
            if not isinstance(record, dict) or record.get("status") not in {"processed", "no_change"}:
                continue
            _assert_input_unchanged(manga, chapter, source, target_manifest, target_hash)
            stage_name, origin = PINCEL_STAGES[treatment]
            operational = stage_chapter(manga, stage_name, chapter, read_legacy=False)
            output_ref = (record.get("output") or {}).get("artifact")
            output = (operational / output_ref).resolve() if isinstance(output_ref, str) else None
            if (output is None or not output.is_relative_to(operational.resolve() / "clean")
                    or not output.is_file() or sha256(output) != record["output"].get("sha256")):
                raise ValueError(f"Output persistido inválido para {page}.")
            old = pages.get(page)
            if old:
                history.append({"page": page, "superseded": old,
                                "superseded_at": datetime.now(timezone.utc).isoformat()})
            destination = staged / page
            shutil.copyfile(output, destination)
            digest = sha256(destination)
            if digest != record["output"]["sha256"]:
                raise ValueError(f"Cópia final divergente para {page}.")
            pages[page] = {"page": page, "artifact": page, "sha256": digest,
                           "origin": origin, "treatment": treatment,
                           "input_sha256": source["sha256"],
                           "input_origin": source["selected_from"],
                           "input_manifest_sha256": source["consolidated_manifest_sha256"],
                           "run_id": record.get("run_id"), "status": record["status"]}
            promoted += 1
        if sha256(target_manifest) != target_hash:
            raise ValueError("Consolidado Final mudou durante a promoção.")
        if promoted:
            write_manifest(staged, _payload(manga, chapter, pages, history,
                                             previous["source_intermediate_manifest_sha256"]))
            promote_stage(staged, target)
    return {"chapter": chapter, "pages_promoted": promoted}


def _assert_input_unchanged(manga, chapter, source, manifest_path, manifest_hash):
    path = Path(source["path"]).resolve()
    if (not path.is_relative_to(Path(manga).resolve()) or not path.is_file()
            or sha256(path) != source["sha256"]
            or Path(source["consolidated_manifest"]).resolve() != manifest_path.resolve()
            or sha256(manifest_path) != manifest_hash
            or source.get("consolidated_manifest_sha256") != manifest_hash):
        raise ValueError("Versão vigente mudou durante a execução do Pincel.")


def _load_existing(target, manga, chapter):
    if not target.exists():
        return None
    manifest = target / "json" / MANIFEST
    if not manifest.is_file():
        raise ValueError("Consolidado Final existente sem manifesto.")
    return read_manifest(manifest, manga, chapter)


def _payload(manga, chapter, pages, history, intermediate_hash):
    return {"schema": SCHEMA, "version": 1, "provider": Path(manga).parent.name,
            "manga": Path(manga).name, "chapter": chapter,
            "source_intermediate_manifest_sha256": intermediate_hash,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "page_count": len(pages), "pages": pages, "history": history}
