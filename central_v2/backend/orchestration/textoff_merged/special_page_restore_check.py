"""Compare a restored page with the actual image approved in Check."""
from pathlib import Path

import cv2
import numpy as np

from central_v2.backend.orchestration.textoff_special.artifacts import sha256

from .special_styled_source import detection_input


def compare_check(manga: Path, provider: str, chapter: str, page: str,
                  source: Path, special: dict) -> dict:
    rows = [row for row in (special.get("treatments") or {}).get("estilizado", [])
            if isinstance(row, dict) and row.get("page") == page]
    if not rows:
        return {"status": "not_applicable", "execution_compatible": True,
                "roi_different_pixels": 0, "outside_roi_different_pixels": 0}
    try:
        detections = [detection_input(manga, provider, chapter, page,
                                      row["id"], row["box_pixels"]) for row in rows]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return {"status": "unavailable", "execution_compatible": False,
                "roi_compatible": False, "roi_different_pixels": None,
                "outside_roi_different_pixels": None,
                "reason": f"Imagem de revisão do Check indisponível: {exc}"}
    if len({item["sha256"] for item in detections}) != 1:
        raise ValueError("Check usa imagens divergentes para a mesma página.")
    check = Path(detections[0]["path"])
    before = cv2.imread(str(source), cv2.IMREAD_UNCHANGED)
    reviewed = cv2.imread(str(check), cv2.IMREAD_UNCHANGED)
    if before is None or reviewed is None or before.shape != reviewed.shape:
        raise ValueError("Imagem restaurada e revisão do Check têm dimensões incompatíveis.")
    changed = before != reviewed if before.ndim == 2 else np.any(before != reviewed, axis=2)
    approved = np.zeros(changed.shape, dtype=bool)
    rois = []
    for row in rows:
        roi = row["box_pixels"]
        x, y, width, height = (roi[key] for key in ("x", "y", "width", "height"))
        approved[y:y + height, x:x + width] = True
        rois.append({"id": row["id"], "box_pixels": roi,
                     "different_pixels": int(changed[y:y + height, x:x + width].sum())})
    inside = int(np.count_nonzero(changed & approved))
    outside = int(np.count_nonzero(changed & ~approved))
    result = {"status": "compatible" if inside == outside == 0 else "blocked",
              "execution_compatible": inside == outside == 0,
              "roi_compatible": inside == 0,
              "restored_sha256": sha256(source), "check_image_sha256": detections[0]["sha256"],
              "check_image_path": str(check), "rois": rois,
              "roi_different_pixels": inside,
              "outside_roi_different_pixels": outside}
    if inside:
        result["reason"] = "A ROI aprovada diverge da imagem restaurada; revise a decisão no Check."
    elif outside:
        result["reason"] = ("A ROI coincide, mas há diferenças fora dela; o Artístico pode "
                            "escrever além da ROI. Revise a origem antes de executar.")
    if sha256(source) != result["restored_sha256"] or sha256(check) != result["check_image_sha256"]:
        raise ValueError("Imagem de restauração ou do Check mudou durante a comparação.")
    return result


def restored_block_reason(manga: Path, provider: str, chapter: str, page: str) -> str | None:
    """Return why an initial Artístico job cannot use a restored page."""
    from .final_consolidated import read_final_page
    from .special_treatments_manifest import manifest_path
    import json

    record, image, _digest = read_final_page(manga, chapter, page)
    if not record.get("restoration_id"):
        return None
    special = json.loads(manifest_path(manga, chapter).read_text(encoding="utf-8"))
    result = compare_check(manga, provider, chapter, page, image, special)
    if not result["execution_compatible"]:
        return "Execução Artístico bloqueada após restauração: " + result["reason"]
    return None


def require_restored_compatibility(manga: Path, provider: str, chapter: str,
                                   page: str) -> None:
    """Reject an initial Artístico job before starting a worker on a restored page."""
    reason = restored_block_reason(manga, provider, chapter, page)
    if reason:
        raise ValueError(reason)
