"""Execute and query the independent, review-only styled-balloon analysis."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

from .artifact_paths import artifact_file, artifact_ref, json_file
from .artifact_migration import mirror_stage_chapter
from .execution import validate_selection
from .manifests import _manifest_matches_merge, _stage_manifest, _stage_manifest_sha256
from .runtime import REPOSITORY_ROOT, python_for
from .styled_balloon_detector import ALGORITHM
from .stages import CONSOLIDATED, LEVEL1, LEVEL3, stage_chapter
from .consolidated import consolidated_is_current, rebuild_consolidated
from .consolidated_artifacts import consolidated_image
from .consolidated import promote_stage
from central_v2.backend.state.sorting import natural_sort_key
from processamento.unificacao_imagens import image_stitcher as v3

STAGE = LEVEL3


def query_level3(manga: Path) -> dict:
    rows = []
    root = manga / "IMG"
    chapters = sorted((path.name for path in root.iterdir() if path.is_dir()),
                      key=natural_sort_key) if root.is_dir() else []
    from .query import query_merged
    merge_rows = {row["chapter"]: row for row in query_merged(manga)["chapters"]}
    for chapter in chapters:
        level1 = _stage_manifest(manga, LEVEL1, chapter)
        ready = _manifest_matches_merge(level1, manga, chapter)
        consolidated_ready = consolidated_is_current(manga, chapter) if ready else False
        path = _manifest_path(manga, chapter)
        try:
            manifest = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            manifest = {}
        current = (ready and consolidated_ready and manifest.get("algorithm") == ALGORITHM
                   and manifest.get("source_consolidated_manifest_sha256") ==
                   _file_sha256(stage_chapter(manga, CONSOLIDATED, chapter, read_legacy=False)
                                / "json/clean-manifest.json")
                   and manifest.get("integrity_ok") is True
                   and manifest.get("source_merge_manifest_sha256") ==
                   _file_sha256(v3.merge_manifest_path(manga / "IMG" / chapter))
                   and bool(json_file(path.parent.parent, "styled-balloon-report.json").is_file()))
        candidate_pages = _candidate_pages(path.parent.parent) if current else []
        rows.append({
            "chapter": chapter, "merge_valid": bool(merge_rows.get(chapter, {}).get("merge_valid")),
            "merge_count": int(merge_rows.get(chapter, {}).get("merge_count") or 0),
            "cleaned": current, "selectable": ready and not current,
            "level3_status": "processed" if current else "pending" if ready else "missing_level1",
            "pages_analyzed": int(manifest.get("pages_analyzed") or 0) if current else 0,
            "candidate_count": int(manifest.get("candidate_count") or 0) if current else 0,
            "candidate_pages": candidate_pages,
        })
    return {"chapters": rows, "total": len(rows)}


def execute_level3(manga: Path, chapters: list[str], progress, preflight=None) -> list[dict]:
    selected = validate_selection(manga, chapters)
    rows = {row["chapter"]: row for row in query_level3(manga)["chapters"]}
    results = []
    for index, chapter in enumerate(selected, 1):
        if preflight:
            preflight()
        row = rows.get(chapter)
        if not row or not row["selectable"]:
            results.append({"chapter": chapter, "status": "failed", "error": "Consolidado de Nível I/II ausente ou inválido."})
            continue
        try:
            result = _analyze_chapter(manga, chapter)
            results.append({"chapter": chapter, "status": "ok", **result})
        except Exception as exc:
            results.append({"chapter": chapter, "status": "failed", "error": str(exc)})
        progress(chapter, {"stage": "level3", "percent": round(index * 100 / len(selected)),
                           "completed": index, "total": len(selected),
                           "message": f"Nível III: Cap. {chapter} analisado."})
    return results


def _analyze_chapter(manga: Path, chapter: str) -> dict:
    merge_chapter = manga / "IMG" / chapter
    merge_manifest = v3.merge_manifest_path(merge_chapter)
    level1 = _stage_manifest(manga, LEVEL1, chapter)
    source_hash = _stage_manifest_sha256(manga, LEVEL1, chapter)
    merge_hash = _file_sha256(merge_manifest)
    if not consolidated_is_current(manga, chapter):
        rebuild_consolidated(manga, chapter)
    consolidated_dir = stage_chapter(manga, CONSOLIDATED, chapter, read_legacy=False)
    consolidated_manifest = json.loads((consolidated_dir / "json/clean-manifest.json").read_text(encoding="utf-8"))
    consolidated_hash = _file_sha256(consolidated_dir / "json/clean-manifest.json")
    images = [consolidated_image(manga, chapter, Path(name).name)
              for name in consolidated_manifest.get("clean_artifacts", [])]
    if (not images or any(path is None for path in images)
            or [path.name for path in images] != [Path(name).stem + "_clean" + Path(name).suffix
                                                  for name in level1.get("source_artifacts", [])]):
        raise ValueError("Imagens consolidadas não correspondem às páginas limpas de Nível I/II.")
    source_hashes = [_sha256(path) for path in images]
    target = stage_chapter(manga, STAGE, chapter, read_legacy=False)
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f".level3-{chapter}-", dir=target.parent) as temp:
        staged = Path(temp) / "stage"
        report_path = staged / "json/styled-balloon-report.json"
        request_path = Path(temp) / "request.json"
        request_path.write_text(json.dumps({"images": [str(path) for path in images],
                                            "report": str(report_path)}), encoding="utf-8")
        python = python_for("merged_nivel_i")
        command = [str(python), "-m", "central_v2.backend.orchestration.textoff_merged.level3_styled_worker",
                   str(request_path)]
        completed = subprocess.run(command, cwd=REPOSITORY_ROOT, capture_output=True,
                                   text=True, timeout=1800)
        if completed.returncode:
            raise RuntimeError((completed.stderr or completed.stdout or "Detector Nível III falhou.")[-2000:])
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if (_stage_manifest_sha256(manga, LEVEL1, chapter) != source_hash
                or _file_sha256(consolidated_dir / "json/clean-manifest.json") != consolidated_hash
                or _file_sha256(merge_manifest) != merge_hash
                or [_sha256(path) for path in images] != source_hashes):
            raise RuntimeError("Os artefatos de entrada mudaram durante a análise.")
        manifest = {
            "schema_version": 1, "algorithm": ALGORITHM, "source_stage": CONSOLIDATED,
            "integrity_ok": report.get("images_analyzed") == len(images),
            "source_level1_manifest_sha256": source_hash,
            "source_level2_manifest_sha256": consolidated_manifest.get("source_level2_manifest_sha256"),
            "source_consolidated_manifest_sha256": consolidated_hash,
            "source_merge_manifest_sha256": merge_hash,
            "source_artifacts": [path.name for path in images],
            "source_artifact_sha256": source_hashes,
            "images_analyzed": report.get("images_analyzed"),
            "candidate_count": report.get("candidate_count"),
            "status": "experimental_review_only",
            "report": artifact_ref("json", report_path.name),
        }
        (staged / "json/clean-manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        promote_stage(staged, target)
    mirror_stage_chapter(manga, "mapear", chapter)
    return {"pages": len(images), "candidate_count": int(report.get("candidate_count") or 0),
            "candidate_types": report.get("candidate_types", {}),
            "manifest": str(target / "json/clean-manifest.json")}


def _manifest_path(manga: Path, chapter: str) -> Path:
    return stage_chapter(manga, STAGE, chapter, read_legacy=False) / "json/clean-manifest.json"


def _candidate_pages(chapter_dir: Path) -> list[dict]:
    try:
        report = json.loads(json_file(chapter_dir, "styled-balloon-report.json").read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return []
    pages = []
    for page in report.get("pages", []):
        candidates = page.get("styled_balloon_candidates") if isinstance(page, dict) else None
        if not candidates or not isinstance(page.get("source"), str):
            continue
        pages.append({"source": page["source"], "candidates": [
            {"bbox": item.get("bbox"), "candidate_type": item.get("candidate_type"),
             "segmenter_confidence": item.get("segmenter_confidence"),
             "features": item.get("features", {})}
            for item in candidates if isinstance(item, dict) and _valid_candidate(item)
        ]})
    return [page for page in pages if page["candidates"]]


def _valid_candidate(item: dict) -> bool:
    bbox = item.get("bbox")
    return (isinstance(bbox, list) and len(bbox) == 4
            and all(isinstance(value, (int, float)) for value in bbox)
            and isinstance(item.get("candidate_type"), str))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _file_sha256(path: Path) -> str | None:
    try:
        return _sha256(path)
    except OSError:
        return None
