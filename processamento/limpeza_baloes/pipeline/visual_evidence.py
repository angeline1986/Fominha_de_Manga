"""Milestone 1C — visual evidence only; no visual classification or routing.

Measures color/spatial characteristics around each CTD candidate while excluding
the candidate text region conservatively. The measurements are evidence, not
decisions: visual_profile remains INCERTO and routing remains REVIEW.
"""
from __future__ import annotations
from pathlib import Path
from typing import Any

ALGORITHM = "textoff_pipeline_visual_evidence_v1"
CONTEXT_EXPANSION_RATIO = 0.35
TEXT_EXCLUSION_DILATION_RATIO = 0.08
MIN_DILATION_PX = 4
MAX_DILATION_PX = 24

def _deps():
    try:
        import cv2
        import numpy as np
    except ImportError as exc:
        raise RuntimeError("Visual Evidence requer cv2 e numpy.") from exc
    return cv2, np

def _clip(v, lo, hi):
    return max(lo, min(hi, v))

def analyze_page(source_image: Path, candidates: list[dict[str, Any]]) -> dict[str, Any]:
    cv2, np = _deps()
    source_image = Path(source_image).resolve()
    image = cv2.imread(str(source_image))
    if image is None:
        raise RuntimeError(f"Visual Evidence falhou ao ler: {source_image}")
    h, w = image.shape[:2]

    evidence = {}
    for c in candidates:
        x1,y1,x2,y2 = map(int, c["bbox"])
        bw, bh = x2-x1, y2-y1
        ex, ey = int(round(bw*CONTEXT_EXPANSION_RATIO)), int(round(bh*CONTEXT_EXPANSION_RATIO))
        rx1, ry1 = _clip(x1-ex,0,w), _clip(y1-ey,0,h)
        rx2, ry2 = _clip(x2+ex,0,w), _clip(y2+ey,0,h)
        roi = image[ry1:ry2, rx1:rx2]
        if roi.size == 0:
            raise ValueError(f"ROI visual vazio para {c['candidate_id']}")

        # Exclude the CTD bbox plus a small dilation. This intentionally avoids
        # treating black glyph pixels as background statistics in 1C.
        local_mask = np.ones(roi.shape[:2], dtype=np.uint8)
        dilation = int(round(min(bw,bh)*TEXT_EXCLUSION_DILATION_RATIO))
        dilation = _clip(dilation, MIN_DILATION_PX, MAX_DILATION_PX)
        tx1 = _clip(x1-rx1-dilation, 0, roi.shape[1])
        ty1 = _clip(y1-ry1-dilation, 0, roi.shape[0])
        tx2 = _clip(x2-rx1+dilation, 0, roi.shape[1])
        ty2 = _clip(y2-ry1+dilation, 0, roi.shape[0])
        local_mask[ty1:ty2, tx1:tx2] = 0
        valid = local_mask > 0
        count = int(np.count_nonzero(valid))

        item = {
            "algorithm": ALGORITHM,
            "context_expansion_ratio": CONTEXT_EXPANSION_RATIO,
            "text_exclusion_dilation_px": dilation,
            "background_pixels": count,
            "measurement_status": "OK" if count else "INSUFFICIENT_BACKGROUND",
        }
        if count:
            hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            sat = hsv[:,:,1][valid].astype(np.float32)
            bgr = roi[valid].astype(np.float32)
            lum = gray[valid].astype(np.float32)

            item.update({
                "saturation_mean": round(float(sat.mean()),4),
                "saturation_p90": round(float(np.percentile(sat,90)),4),
                "rgb_std_mean": round(float(np.std(bgr,axis=0).mean()),4),
                "luminance_std": round(float(lum.std()),4),
            })

            # Spatial evidence: compare valid-pixel means in left/right,
            # top/bottom and four quadrants. These are descriptive only.
            def mean_lum(mask):
                vals = gray[(valid & mask)]
                return float(vals.mean()) if vals.size else None

            rh,rw = roi.shape[:2]
            yy,xx = np.indices((rh,rw))
            left, right = xx < rw/2, xx >= rw/2
            top, bottom = yy < rh/2, yy >= rh/2
            means = {
                "left": mean_lum(left), "right": mean_lum(right),
                "top": mean_lum(top), "bottom": mean_lum(bottom),
                "q1": mean_lum(left & top), "q2": mean_lum(right & top),
                "q3": mean_lum(left & bottom), "q4": mean_lum(right & bottom),
            }
            qvals=[v for k,v in means.items() if k.startswith("q") and v is not None]
            item["spatial_luminance"] = {
                "left_right_delta": round(abs(means["left"]-means["right"]),4) if means["left"] is not None and means["right"] is not None else None,
                "top_bottom_delta": round(abs(means["top"]-means["bottom"]),4) if means["top"] is not None and means["bottom"] is not None else None,
                "quadrant_range": round(max(qvals)-min(qvals),4) if len(qvals)>=2 else None,
            }
        evidence[c["candidate_id"]] = item

    return {"algorithm": ALGORITHM, "source_image": str(source_image), "candidates": evidence}
