"""Prepare consolidated candidates without changing their live directories."""
import json
from datetime import datetime, timezone
from pathlib import Path
import shutil

from central_v2.backend.orchestration.textoff_special.artifacts import sha256
from central_v2.backend.orchestration.textoff_merged.artifact_paths import artifact_ref, prepare_artifact_dirs
from central_v2.backend.orchestration.textoff_merged.consolidated import (
    ALGORITHM, _select_artifacts, _valid_level2,
)
from central_v2.backend.orchestration.textoff_merged.final_consolidated import (
    AUTOMATIC_ORIGINS, MANIFEST as FINAL_MANIFEST, STAGE as FINAL_STAGE,
    TREATMENT_ORIGINS, _payload as final_payload,
)
from central_v2.backend.orchestration.textoff_merged.final_consolidated_manifest import (
    read_manifest, write_manifest,
)
from central_v2.backend.orchestration.textoff_merged.manifests import (
    _manifest_matches_merge, _stage_manifest, _stage_manifest_sha256,
)
from central_v2.backend.orchestration.textoff_merged.stages import (
    COMBO_TURBO, CONSOLIDATED, LEVEL1, LEVEL2, stage_chapter,
)


def prepare_candidates(manga, chapter, combo_stage, combo_manifest, logical_stage, final_stage):
    manga = Path(manga).resolve()
    level1, level1_hash = _stage_manifest(manga, LEVEL1, chapter), _stage_manifest_sha256(manga, LEVEL1, chapter)
    if not level1_hash or not _manifest_matches_merge(level1, manga, chapter):
        raise ValueError("Manifesto Nível I não corresponde ao MERGE vigente.")
    level2, level2_dir, level2_hash = _valid_level2(manga, chapter, level1, level1_hash)
    logical_path = stage_chapter(manga, CONSOLIDATED, chapter, read_legacy=False) / "json/clean-manifest.json"
    old_logical_hash = sha256(logical_path) if logical_path.is_file() else None
    current_logical = _current_logical(manga, chapter)
    superseded_logical = old_logical_hash if old_logical_hash and current_logical is None else None
    if current_logical:
        selections = list(current_logical["selections"])
    else:
        names = level1["source_artifacts"]
        selected = _select_artifacts(names, level1, stage_chapter(manga, LEVEL1, chapter),
                                     level2, level2_dir)
        selections = [_selection(name, stage, path) for name, (path, stage) in zip(names, selected)]
    final_path = stage_chapter(manga, FINAL_STAGE, chapter, read_legacy=False)
    previous_final = _read_final(final_path, manga, chapter)
    treated = {page for page, row in (previous_final or {}).get("pages", {}).items()
               if row.get("origin") in TREATMENT_ORIGINS.values()}
    for page, row in combo_manifest.get("run_pages", {}).items():
        if row.get("status") != "COMPOSED" or page in treated:
            continue
        selection = {"source": page, "selected_from": COMBO_TURBO,
            "artifact": artifact_ref("clean", Path(page).stem + "_clean.png"),
            "source_artifact": row["artifact"], "sha256": row["sha256"]}
        old = next((item for item in selections if item.get("source") == page), None)
        if old is None:
            raise ValueError(f"Página Combo ausente do conjunto de origem: {page}.")
        selections[selections.index(old)] = selection
    logical_payload = _write_logical(manga, chapter, logical_stage, selections,
        level1, level1_hash, level2_hash, combo_manifest, superseded_logical)
    _write_final(manga, chapter, combo_stage, logical_stage, logical_payload,
                 final_stage, previous_final)
    return logical_payload


def _current_logical(manga, chapter):
    from central_v2.backend.orchestration.textoff_merged.consolidated import consolidated_is_current
    folder = stage_chapter(manga, CONSOLIDATED, chapter, read_legacy=False)
    pathname = folder / "json" / "clean-manifest.json"
    if not pathname.exists():
        if folder.exists() and any(folder.iterdir()):
            raise ValueError("Consolidado lógico parcial; publicação bloqueada.")
        return None
    payload = json.loads(pathname.read_text(encoding="utf-8"))
    if (not isinstance(payload, dict) or not isinstance(payload.get("selections"), list)
            or not isinstance(payload.get("source_artifacts"), list)):
        raise ValueError("Manifesto lógico inválido; publicação bloqueada.")
    return payload if consolidated_is_current(manga, chapter) else None


def _selection(page, stage, path):
    return {"source": page, "selected_from": stage,
            "artifact": artifact_ref("clean", Path(page).stem + "_clean.png"),
            "sha256": sha256(path)}


def _write_logical(manga, chapter, folder, selections, level1, level1_hash,
                   level2_hash, combo_manifest, superseded_logical):
    combo_hash = combo_manifest.get("_candidate_sha256")
    if not combo_hash:
        raise ValueError("Manifesto Combo candidato sem hash.")
    folder.mkdir(parents=True, exist_ok=False)
    prepare_artifact_dirs(folder)
    for item in selections:
        if item["selected_from"] == LEVEL2:
            source = stage_chapter(manga, LEVEL2, chapter) / Path(item["artifact"])
            destination = folder / item["artifact"]
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            if sha256(destination) != item["sha256"]:
                raise ValueError("Cópia candidata do consolidado lógico divergiu.")
    names = level1["source_artifacts"]
    payload = {"schema_version": 1, "algorithm": ALGORITHM,
        "source_stage": CONSOLIDATED, "integrity_ok": True, "source_artifacts": names,
        "source_level1_manifest_sha256": level1_hash,
        "source_level2_manifest_sha256": level2_hash,
        "source_combo_manifest_sha256": combo_hash,
        "supersedes_logical_manifest_sha256": superseded_logical,
        "clean_artifacts": [item["artifact"] for item in selections],
        "outputs_total": len(selections), "selections": selections}
    (folder / "json" / "clean-manifest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def _read_final(folder, manga, chapter):
    manifest = folder / "json" / FINAL_MANIFEST
    if not manifest.exists():
        if folder.exists() and any(folder.iterdir()):
            raise ValueError("Consolidado Final parcial; publicação bloqueada.")
        return None
    return read_manifest(manifest, manga, chapter)


def _write_final(manga, chapter, combo_stage, logical_stage, logical, folder, previous):
    folder.mkdir(parents=True, exist_ok=False)
    if previous:
        source = stage_chapter(manga, FINAL_STAGE, chapter, read_legacy=False)
        shutil.copytree(source, folder, dirs_exist_ok=True)
    else:
        prepare_artifact_dirs(folder)
    pages = dict((previous or {}).get("pages", {}))
    history = list((previous or {}).get("history", []))
    for item in logical["selections"]:
        page, origin = item["source"], AUTOMATIC_ORIGINS[item["selected_from"]]
        old = pages.get(page)
        if old and old.get("origin") in TREATMENT_ORIGINS.values():
            continue
        if old and old.get("sha256") == item["sha256"] and old.get("origin") == origin:
            continue
        if item["selected_from"] == COMBO_TURBO:
            image = combo_stage / item["source_artifact"]
        else:
            image = stage_chapter(manga, item["selected_from"], chapter) / item["artifact"]
        if not image.is_file() or sha256(image) != item["sha256"]:
            raise ValueError(f"Imagem candidata final inválida: {page}.")
        if old:
            previous_image = folder / page
            if (not previous_image.is_file() or sha256(previous_image) != old.get("sha256")):
                raise ValueError(f"Imagem final anterior inválida: {page}.")
            archived = Path("history") / old["sha256"] / page
            archive_path = folder / archived
            archive_path.parent.mkdir(parents=True, exist_ok=True)
            if not archive_path.exists():
                shutil.copy2(previous_image, archive_path)
            if sha256(archive_path) != old["sha256"]:
                raise ValueError(f"Arquivo histórico divergente: {page}.")
            history.append({"page": page, "superseded": old,
                "superseded_at": datetime.now(timezone.utc).isoformat(),
                "reason": "combo_publication", "archived_artifact": archived.as_posix(),
                "archived_sha256": old["sha256"]})
        shutil.copyfile(image, folder / page)
        pages[page] = {"page": page, "artifact": page, "sha256": item["sha256"],
                       "origin": origin, "treatment": None, "input_sha256": None}
    logical_manifest = logical_stage / "json" / "clean-manifest.json"
    write_manifest(folder, final_payload(manga, chapter, pages, history,
                                          sha256(logical_manifest)))
