"""Isolated adapters for the existing Sólidos and Glass engines."""
import json
import os
import shutil
import tempfile
from pathlib import Path

from processamento.unificacao_imagens import image_stitcher as v3
from central_v2.backend.orchestration.textoff_merged.level2_process import process as run_glass
from central_v2.backend.orchestration.textoff_merged.level2_manual_protection import load_level1_protection_context
from central_v2.backend.orchestration.textoff_merged.level2_validation import build_output_manifest, validated_candidate_pages
from central_v2.backend.orchestration.textoff_merged.level2_provenance import (
    assert_report_artifacts_current, validate_protection_provenance,
    validate_report_provenance,
)
from central_v2.backend.orchestration.textoff_merged.manifests import _stage_manifest, _stage_manifest_sha256
from central_v2.backend.orchestration.textoff_merged.solid_stage import execute_chapter as run_solids
from central_v2.backend.orchestration.textoff_merged.stages import LEVEL1, LEVEL2, stage_chapter
from central_v2.backend.orchestration.textoff_special.artifacts import sha256


def run_solids_isolated(manga, provider, chapter, pages, reusable_pages):
    folder = stage_chapter(manga, "05_AUTO_CLEANER_SOLIDOS", chapter, read_legacy=False)
    document = {"provider": provider, "obra": manga.name, "capitulo": chapter}
    if not folder.exists() or not reusable_pages:
        if folder.exists():
            shutil.rmtree(folder)
        return run_solids(manga, document, chapter, candidate_pages=set(pages))
    parent = Path(tempfile.mkdtemp(prefix="combo-solids-"))
    staged = parent / "stage"
    try:
        run_solids(manga, document, chapter, candidate_pages=set(pages), output_dir=staged)
        old_path, new_path = folder / "solid-white-manifest.json", staged / "solid-white-manifest.json"
        old, new = json.loads(old_path.read_text()), json.loads(new_path.read_text())
        for row in new["pages"]:
            stem = Path(row["page"]).stem
            for kind, name in (("clean", f"{stem}_clean.png"), ("mask", f"{stem}_mask.png")):
                target = folder / kind / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(staged / kind / name, target)
        old["pages"] = [row for row in old["pages"] if row["page"] not in pages] + new["pages"]
        new_ids = {row["id"] for row in new["regions"]}
        old["regions"] = [row for row in old["regions"] if row["id"] not in new_ids] + new["regions"]
        temporary = old_path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(old, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, old_path)
    finally:
        shutil.rmtree(parent, ignore_errors=True)


def run_glass_isolated(manga, provider, chapter, pages, reusable_pages, progress):
    source = v3.merge_output_dir(manga / "IMG" / chapter)
    level1 = stage_chapter(manga, LEVEL1, chapter)
    stage = stage_chapter(manga, LEVEL2, chapter, read_legacy=False)
    previous_manifest, previous_report = (stage / "json" / "clean-manifest.json",
                                           stage / "json" / "level2-transparent-report.json")
    old_manifest = json.loads(previous_manifest.read_text()) if reusable_pages and previous_manifest.is_file() else None
    old_report = json.loads(previous_report.read_text()) if reusable_pages and previous_report.is_file() else None
    if stage.exists() and not reusable_pages:
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    report_path = stage / "json" / "level2-transparent-report.json"
    protections, authority = load_level1_protection_context(manga, provider, manga.name, chapter)
    try:
        report = run_glass(source, level1, stage, report_path, candidate_pages=set(pages),
                           protected_occurrences=protections, protection_source=authority)
        current_level1_hash = _stage_manifest_sha256(manga, LEVEL1, chapter)
        validate_report_provenance(report["pages"], current_level1_hash,
                                   report.get("source_level1_manifest_sha256"), chapter)
        validate_protection_provenance(report, report["pages"], authority, protections, chapter)
        assert_report_artifacts_current(report, source, level1, stage)
        _assert_authority_current(manga, authority)
        report["report_reference"] = "json/level2-transparent-report.json"
        verified = validated_candidate_pages(report, set(pages), stage, level1)
        if reusable_pages:
            keep = set(reusable_pages)
            verified = [row for row in old_manifest["page_results"] if row.get("source") in keep] + verified
            report["pages"] = [row for row in old_report["pages"] if row.get("source") in keep] + report["pages"]
            report["pages_analyzed"] = len(report["pages"])
        candidates = set(pages) | set(reusable_pages)
        images = v3.merge_artifact_files(source)
        level1_manifest = _stage_manifest(manga, LEVEL1, chapter)
        level1_hash = _stage_manifest_sha256(manga, LEVEL1, chapter)
        if level1_hash != current_level1_hash:
            raise ValueError(f"Manifesto do Nível I mudou durante o Cap. {chapter}.")
        _assert_authority_current(manga, authority)
        output, _ = build_output_manifest(report, verified, images, candidates,
                                           level1_manifest, level1_hash)
        (stage / "json" / "clean-manifest.json").write_text(
            json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if callable(progress):
            progress({"chapter": chapter, "stage": "GLASS", "status": "COMPLETED"})
        return []
    except (OSError, ValueError, TypeError, RuntimeError) as exc:
        return [{"stage": "GLASS", "reason": "EXECUTION_FAILED", "detail": str(exc)}]


def _assert_authority_current(manga, authority):
    path = Path(manga) / authority["path"] if authority.get("path") else None
    current = sha256(path) if path and path.is_file() else None
    if current != authority.get("sha256"):
        raise ValueError("Fonte de proteções mudou durante a execução Combo Glass.")


def level1_image(manga, chapter, page):
    return stage_chapter(manga, LEVEL1, chapter) / "clean" / f"{Path(page).stem}_clean.png"


def solid_image(manga, chapter, page):
    return stage_chapter(manga, "05_AUTO_CLEANER_SOLIDOS", chapter, read_legacy=False) / "clean" / f"{Path(page).stem}_clean.png"


def glass_images(manga, chapter, page):
    folder = stage_chapter(manga, LEVEL2, chapter)
    manifest = json.loads((folder / "json" / "clean-manifest.json").read_text(encoding="utf-8"))
    row = next(item for item in manifest["page_results"] if item.get("source") == page)
    clean = folder / row["clean"] if row.get("clean") else level1_image(manga, chapter, page)
    return clean, folder / row["mask"]


def source_signature(manga, provider, chapters):
    """Hash only selected chapters and their Combo authority/artifact stages."""
    root, files = Path(manga).resolve(), set()
    for chapter in chapters:
        files.update(path for path in (root / "IMG" / chapter).rglob("*") if path.is_file())
        for stage in (LEVEL1, LEVEL2, "05_AUTO_CLEANER_SOLIDOS", "RESIDUE_OCCURRENCES"):
            folder = stage_chapter(root, stage, chapter, read_legacy=False)
            if folder.is_dir():
                files.update(path for path in folder.rglob("*") if path.is_file())
        from central_v2.backend.orchestration.textoff_merged.auto_cleaner_check_manifest import manifest_path
        check = manifest_path(root, chapter)
        if check.is_file():
            files.add(check)
    pairs = [(str(path.relative_to(root)), sha256(path)) for path in sorted(files)]
    return sha256_bytes(json.dumps(pairs, ensure_ascii=False, separators=(",", ":")).encode())


def sha256_bytes(value):
    import hashlib
    return hashlib.sha256(value).hexdigest()
