"""Build and read the immutable per-chapter Combo publication manifest."""
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import uuid

from central_v2.backend.orchestration.textoff_special.artifacts import sha256

from central_v2.backend.orchestration.textoff_merged.artifact_paths import prepare_artifact_dirs
from central_v2.backend.orchestration.textoff_merged.stages import COMBO_TURBO, provider_name, stage_chapter

SCHEMA = "textoff_combo_turbo_manifest_v1"
MANIFEST = "combo-manifest.json"


def path_for(manga, chapter):
    return stage_chapter(Path(manga), COMBO_TURBO, chapter, read_legacy=False)


def read_manifest(manga, chapter, folder=None):
    folder = Path(folder) if folder else path_for(manga, chapter)
    manifest = folder / "json" / MANIFEST
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    if (payload.get("schema") != SCHEMA or payload.get("version") != 1
            or payload.get("provider") != provider_name(manga)
            or payload.get("manga") != Path(manga).name
            or payload.get("chapter") != chapter
            or payload.get("integrity_ok") is not True
            or not isinstance(payload.get("pages"), dict)):
        raise ValueError("Manifesto Combo inválido ou incompatível.")
    return payload


def prepare_generation(manga, chapter, staged, pages, *, run_id=None, previous=None):
    """Copy prior generations and add this run without overwriting artifacts."""
    staged = Path(staged)
    if staged.exists():
        raise ValueError("Estágio Combo temporário já existe.")
    prior_folder = path_for(manga, chapter)
    if previous is not None:
        shutil.copytree(prior_folder, staged)
    else:
        prepare_artifact_dirs(staged)
        (staged / "generations").mkdir()
    identity = run_id or uuid.uuid4().hex
    if not isinstance(identity, str) or not identity or Path(identity).name != identity:
        raise ValueError("Identificador de execução Combo inválido.")
    generation = staged / "generations" / identity
    if generation.exists():
        raise ValueError("Geração Combo já publicada.")
    prepare_artifact_dirs(generation)
    old_pages = dict(previous.get("pages", {})) if previous else {}
    history = list(previous.get("history", [])) if previous else []
    if previous:
        from .publication_validation import validate_published_page
        for page, row in list(old_pages.items()):
            if row.get("status") == "COMPOSED" and validate_published_page(
                    manga, chapter, page, row.get("sha256")) is None:
                old_pages[page] = {**row, "status": "STALE",
                                   "reasons": ["SOURCE_DEPENDENCY_CHANGED"]}
                history.append({"page": page, "superseded": row,
                    "reason": "source_dependency_changed",
                    "superseded_at": datetime.now(timezone.utc).isoformat()})
    merged = dict(old_pages)
    run_pages = {}
    for page, row in pages.items():
        old = merged.get(page)
        if row.get("status") == "COMPOSED":
            artifact = f"generations/{identity}/clean/{Path(page).stem}_combo.png"
            report_ref = f"generations/{identity}/json/{Path(page).stem}_report.json"
            shutil.copy2(row["image"], staged / artifact)
            shutil.copy2(row["report_file"], staged / report_ref)
            if (sha256(staged / artifact) != row.get("result_sha256")
                    or sha256(staged / report_ref) != row.get("report_sha256")):
                raise ValueError(f"Cópia de geração Combo divergiu: {page}.")
            row = {key: value for key, value in row.items()
                   if key not in {"image", "report_file"}}
            row.update(generation=identity, artifact=artifact, report=report_ref,
                       sha256=row["result_sha256"])
            if old is not None:
                history.append({"page": page, "superseded": old,
                                "superseded_at": datetime.now(timezone.utc).isoformat()})
            merged[page] = row
            run_pages[page] = row
        elif page not in merged:
            merged[page] = row
            run_pages[page] = row
        else:
            run_pages[page] = row
    source_refs = _source_refs(manga, chapter)
    payload = {"schema": SCHEMA, "version": 1, "provider": provider_name(manga),
        "manga": Path(manga).name, "chapter": chapter, "run_id": identity,
        "created_at": datetime.now(timezone.utc).isoformat(), "integrity_ok": True,
        "status": _status(pages), "sources": source_refs, "pages": merged,
        "run_pages": run_pages,
        "history": history, "page_count": len(merged),
        "composed_count": sum(row.get("status") == "COMPOSED" for row in merged.values()),
        "no_work_count": sum(row.get("status") == "NO_WORK" for row in merged.values()),
        "blocked_count": sum(row.get("status") in {"CONFLICT", "BLOCKED", "FAILED"}
                              for row in merged.values())}
    manifest_path = staged / "json" / MANIFEST
    manifest_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    payload["_candidate_sha256"] = sha256(manifest_path)
    return payload, generation


def _source_refs(manga, chapter):
    from central_v2.backend.orchestration.textoff_merged.auto_cleaner_check_manifest import manifest_path
    from central_v2.backend.orchestration.textoff_merged.stages import LEVEL1, LEVEL2, stage_chapter
    refs = {}
    for name, path in (("check", manifest_path(manga, chapter)),
        ("level1", stage_chapter(manga, LEVEL1, chapter) / "json" / "clean-manifest.json"),
        ("glass", stage_chapter(manga, LEVEL2, chapter) / "json" / "clean-manifest.json"),
        ("solids", stage_chapter(manga, "05_AUTO_CLEANER_SOLIDOS", chapter,
                                  read_legacy=False) / "solid-white-manifest.json")):
        refs[name] = {"path": str(path.relative_to(manga)),
                      "sha256": sha256(path) if path.is_file() else None}
    return refs


def _status(pages):
    statuses = {row.get("status") for row in pages.values()}
    return "COMPLETED" if statuses.issubset({"COMPOSED", "NO_WORK"}) else "PARTIAL"
