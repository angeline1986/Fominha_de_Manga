"""Execute and query the independent, review-only styled-balloon analysis."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

from .artifact_paths import artifact_ref
from .artifact_shadow_read import observe_shadow_read
from .artifact_migration import mirror_stage_chapter
from .execution import validate_selection
from .manifests import _stage_manifest, _stage_manifest_sha256
from .runtime import REPOSITORY_ROOT, python_for
from .styled_balloon_detector import ALGORITHM
from .stages import CONSOLIDATED, LEVEL1, LEVEL3, stage_chapter
from .level3_query import query_level3
from .consolidated import consolidated_is_current, rebuild_consolidated
from .consolidated_artifacts import consolidated_image
from .consolidated import promote_stage
from processamento.unificacao_imagens import image_stitcher as v3

STAGE = LEVEL3


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
    observe_shadow_read(manga, "mapear_input_consolidado", chapter)
    consolidated_dir = stage_chapter(manga, CONSOLIDATED, chapter)
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
