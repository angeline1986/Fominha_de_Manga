"""Level I-gated experimental runs for Merged IV and V."""
import json
from pathlib import Path
import tempfile

from .artifact_paths import artifact_file, json_file
from .manifests import _manifest_matches_merge, _stage_manifest
from .query import query_merged_level1
from central_v2.backend.orchestration.textoff_special.artifacts import sha256
from central_v2.backend.orchestration.textoff_special.catalog import STAGING_ROOT
from central_v2.backend.orchestration.textoff_special.execution import preview

TREATMENTS = {"IV": "transparente", "V": "transparente_legacy"}


def query_special_level(manga: Path, level: str) -> dict:
    if level not in TREATMENTS:
        raise ValueError("Nível Merged especial inválido.")
    result = query_merged_level1(manga)
    for row in result["chapters"]:
        manifest = _stage_manifest(manga, "MERGED_NIVEL_I", row["chapter"])
        row["selectable"] = bool(row["merge_valid"] and _manifest_matches_merge(
            manifest, manga, row["chapter"]))
        row["level1_ready"] = row["selectable"]
        row["special_level"] = level
        manifest = _stage_manifest(manga, "MERGED_NIVEL_I", row["chapter"])
        row["level1_pages"] = [Path(item).name for item in manifest.get("clean_artifacts", [])
                               if isinstance(item, str)]
    return result


def execute_special_level(manga: Path, level: str, chapters: list[str], progress,
                          *, preflight=None) -> list[dict]:
    treatment = TREATMENTS.get(level)
    if treatment is None:
        raise ValueError("Nível Merged especial inválido.")
    rows = {row["chapter"]: row for row in query_special_level(manga, level)["chapters"]}
    results = []
    for chapter_index, chapter in enumerate(chapters, 1):
        if preflight:
            preflight()
        row = rows.get(chapter)
        if not row or not row["level1_ready"]:
            results.append({"chapter": chapter, "status": "failed", "error": "Nível I ausente ou inválido."})
            continue
        folder = manga / "FLUXO_SECUNDARIO/04_TEXTO_OFF/MERGED_NIVEL_I" / chapter
        manifest = _stage_manifest(manga, "MERGED_NIVEL_I", chapter)
        report_name = (manifest.get("level1") or {}).get("report")
        report_path = artifact_file(folder, report_name, "json")
        try:
            report = json.loads(report_path.read_text(encoding="utf-8")) if report_path else {}
            pages = {item["source"]: item for item in report.get("pages", [])}
            inputs = manifest.get("clean_artifacts", [])
            page_results = []
            for filename in inputs:
                page_name = Path(filename).name.replace("_clean", "")
                source_page = pages.get(page_name, {})
                balloons = source_page.get("transparent_balloons", [])
                selections = [{"x": b["bbox"][0], "y": b["bbox"][1],
                               "width": b["bbox"][2], "height": b["bbox"][3]}
                              for b in balloons if len(b.get("bbox", [])) == 4]
                if not selections:
                    page_results.append({"filename": Path(filename).name, "status": "no_candidates"})
                    continue
                source = artifact_file(folder, filename, "clean")
                if source is None:
                    raise ValueError(f"Artefato Nível I ausente: {filename}")
                payload = {"treatment": treatment, "level": "MERGED_NIVEL_I",
                           "chapter": chapter, "filename": source.name,
                           "expected_sha256": sha256(source), "selections": selections}
                if level in {"IV", "V"}:
                    STAGING_ROOT.mkdir(parents=True, exist_ok=True)
                    with tempfile.TemporaryDirectory(prefix="textoff-merged-mask-",
                                                     dir=STAGING_ROOT) as temporary:
                        mask = (_legacy_authorization_mask(folder, source_page)
                                if level == "V" else _normal_authorization_mask(folder, source_page))
                        mask_path = Path(temporary) / "authorized.png"
                        import cv2
                        if not cv2.imwrite(str(mask_path), mask):
                            raise RuntimeError(f"Não foi possível preparar a máscara do Nível {level}.")
                        payload["merged_level"] = level
                        payload["preauthorized_mask_path"] = str(mask_path)
                        run = preview(manga, payload)
                page_results.append({"filename": source.name, "status": run["execution_status"],
                                     "run_id": run["run_id"],
                                     "manifest": str(STAGING_ROOT / run["run_id"] / "manifest.json"),
                                     "error": run.get("error")})
            status = "failed" if any(page.get("status") == "failed" for page in page_results) else "ok"
            results.append({"chapter": chapter, "status": status, "pages": page_results})
        except Exception as exc:
            results.append({"chapter": chapter, "status": "failed", "error": str(exc)})
        progress(chapter, {"stage": level.lower(), "percent": round(chapter_index * 100 / len(chapters)),
                           "completed": chapter_index, "total": len(chapters),
                           "message": f"Nível {level}: Cap. {chapter} concluído."})
    return results


def _normal_authorization_mask(folder: Path, page: dict):
    import cv2
    import numpy as np
    from .level2_vision import _authorized_deferred_mask

    deferred_path = artifact_file(folder, page.get("deferred_text_mask_artifact"), "mask")
    labels_path = artifact_file(folder, page.get("transparent_mask_artifact"), "mask")
    deferred = cv2.imread(str(deferred_path), cv2.IMREAD_GRAYSCALE) if deferred_path else None
    labels = cv2.imread(str(labels_path), cv2.IMREAD_UNCHANGED) if labels_path else None
    ids = [balloon.get("mask_label") for balloon in page.get("transparent_balloons", [])
           if type(balloon.get("mask_label")) is int and balloon["mask_label"] > 0]
    if deferred is None or labels is None or labels.shape != deferred.shape or not ids:
        raise ValueError("Nível I não forneceu máscaras válidas para o ajuste fino.")
    mask = _authorized_deferred_mask(deferred, np.isin(labels, ids).astype(np.uint8) * 255)
    if not np.any(mask):
        raise ValueError("Nível I não deixou texto adiado para o ajuste fino.")
    return mask


def _legacy_authorization_mask(folder: Path, page: dict):
    import cv2
    from .level2_vision import AUTHORIZED_DILATION, BASE_DILATION

    deferred_path = artifact_file(folder, page.get("deferred_text_mask_artifact"), "mask")
    deferred = cv2.imread(str(deferred_path), cv2.IMREAD_GRAYSCALE) if deferred_path else None
    if deferred is None:
        raise ValueError("Nível I não forneceu texto adiado para o Nível V.")
    base = cv2.dilate(deferred, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, BASE_DILATION))
    mask = cv2.dilate(base, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, AUTHORIZED_DILATION))
    if not cv2.countNonZero(mask):
        raise ValueError("Nível I não deixou máscara para o Nível V.")
    return mask
