"""Apply persisted Check ROI approval to deferred Degradê candidates only."""
import json

import cv2
import numpy as np


def apply_approved_rois(original, clean_path, mask_path, raw_clean, raw_mask,
                        report_path, boxes):
    report = json.loads(report_path.read_text(encoding="utf-8"))
    pages = report.get("pages") or []
    if len(pages) != 1:
        raise ValueError("Relatório de autorização especial inválido.")
    decisions = {item["component"]: item for item in pages[0]["component_decisions"]}
    count, labels, _, _ = cv2.connectedComponentsWithStats((raw_mask > 0).astype(np.uint8), 8)
    authorized = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
    if authorized is None or raw_clean.shape != original.shape or raw_mask.shape != authorized.shape:
        raise ValueError("Máscaras de autorização especial incompatíveis.")
    selected = []
    for label in range(1, count):
        decision = decisions.get(label)
        if not decision or decision.get("reason") != "transparent_balloon_deferred":
            continue
        component = labels == label
        hits = [index for index, (x, y, width, height) in enumerate(boxes, 1)
                if np.any(component[y:y + height, x:x + width])]
        if hits:
            authorized[component] = raw_mask[component]
            selected.append({"component": label, "roi_hits": hits,
                             "reason": "approved_check_roi_over_transparent_deferred"})
    rebuilt = original.copy()
    rebuilt[authorized > 0] = raw_clean[authorized > 0]
    if not cv2.imwrite(str(mask_path), authorized) or not cv2.imwrite(str(clean_path), rebuilt):
        raise RuntimeError("Falha ao preparar autorização especial Degradê.")
    return selected
