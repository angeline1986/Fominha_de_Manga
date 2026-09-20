"""M2: descriptive geometry and masked zones; never classification or cleaning.

This is distinct from visual_evidence v1, whose rectangular CTD surroundings
can mix balloon surface and scene. Those existing fields retain their meaning.

For binary balloon M and square kernel K:
  INTERIOR = erode(M, K), zero padding outside the image;
  INNER_RING = M minus INTERIOR;
  OUTER_CONTEXT = dilate(M, K) minus M, clipped to the image, then excluding
                  all other segmented balloons.
All clipped CTD rectangles are excluded from statistics, without OCR or labels.
Counts distinguish geometric support, neighboring balloons and text exclusion.
Missing CTD is recorded; even present CTD does not guarantee complete text removal.
Small zones never fall back to another zone. Statistics need min_pixels samples.
Kernel size is a geometric sampling parameter, not a routing threshold.
"""
from __future__ import annotations

import math
from numbers import Integral

import cv2
import numpy as np

ALGORITHM = "textoff_region_evidence_v1"
SCHEMA_VERSION = 1
DEFAULT_KERNEL_SIZE = 9  # Existing guard's sampling width; no guard decisions reused.
DEFAULT_MIN_PIXELS = 2  # At least two samples for descriptive dispersion.


def _size(value, name):
    if len(value) != 2 or any(not isinstance(v, Integral) or v <= 0 for v in value):
        raise ValueError(f"Invalid {name} dimensions")
    return tuple(map(int, value))


def _bbox(value):
    if len(value) != 4 or any(not math.isfinite(float(v)) for v in value):
        raise ValueError("Invalid bbox")
    x1, y1, x2, y2 = map(float, value)
    if x2 <= x1 or y2 <= y1:
        raise ValueError("Invalid bbox geometry")
    return x1, y1, x2, y2


def to_merged_bbox(bbox, *, split_size, merged_size, offset=(0, 0), scale=1.0):
    """CTD pixels / scale + integer split offset = MERGED pixels.

scale is CTD-image pixels per original split pixel (not an inferred scale).
Clipping occurs in the split before translation, never leaking into a neighbor.
Floor/ceil conservatively enclose a rescaled rectangle; source inputs are retained.
"""
    sw, sh = _size(split_size, "split")
    mw, mh = _size(merged_size, "MERGED")
    if len(offset) != 2 or any(not isinstance(v, Integral) for v in offset):
        raise ValueError("Invalid offset")
    ox, oy = map(int, offset)
    if ox < 0 or oy < 0 or ox + sw > mw or oy + sh > mh:
        raise ValueError("Offset/split outside MERGED dimensions")
    if not math.isfinite(scale) or scale <= 0:
        raise ValueError("Invalid scale")
    raw = _bbox(bbox)
    scaled = [math.floor(raw[0]/scale), math.floor(raw[1]/scale),
              math.ceil(raw[2]/scale), math.ceil(raw[3]/scale)]
    clipped = [max(0, scaled[0]), max(0, scaled[1]),
               min(sw, scaled[2]), min(sh, scaled[3])]
    if clipped[2] <= clipped[0] or clipped[3] <= clipped[1]:
        raise ValueError("Candidate outside split")
    return {"bbox": [clipped[0]+ox, clipped[1]+oy, clipped[2]+ox, clipped[3]+oy],
            "input_bbox": list(bbox), "split_bbox": clipped,
            "split_size": [sw, sh], "merged_size": [mw, mh],
            "offset": [ox, oy], "scale": scale,
            "clipped": clipped != scaled, "rounding": "FLOOR_MIN_CEIL_MAX"}


def _stats(image, support, min_pixels):
    n = int(np.count_nonzero(support))
    if n < min_pixels:
        return {"available": False, "reason": "INSUFFICIENT_PIXELS",
                "pixel_count": n, "metrics": None}
    # Convert only selected samples; uint8 OpenCV HSV S and grayscale, not linear luminance.
    pixels = image[support].reshape(-1, 1, 3)
    sat = cv2.cvtColor(pixels, cv2.COLOR_BGR2HSV)[:, 0, 1].astype(np.float64)
    gray = cv2.cvtColor(pixels, cv2.COLOR_BGR2GRAY).astype(np.float64)
    rgb = pixels[:, 0].astype(np.float64)
    return {"available": True, "reason": None, "pixel_count": n,
            "metrics": {"saturation_mean": round(float(sat.mean()), 4),
                        "saturation_p90": round(float(np.percentile(sat, 90)), 4),
                        "gray_mean": round(float(gray.mean()), 4),
                        "gray_std": round(float(gray.std()), 4),
                        "rgb_std_mean": round(float(rgb.std(axis=0).mean()), 4)}}


def measure_regions(image, masks, candidates, *, kernel_size=DEFAULT_KERNEL_SIZE,
                    min_pixels=DEFAULT_MIN_PIXELS):
    """Measure a single segmentation in image coordinates. Inputs are not mutated.

Mask IDs are local to this segmentation. Relations are geometric only: exact
FULL_CONTAINMENT vs PARTIAL_INTERSECTION plus continuous coverage and center
membership, allowing marginal contacts to be inspected without a new threshold.
candidates=None means unavailable CTD; [] means available CTD with zero detections.
"""
    if image.ndim != 3 or image.shape[2] != 3 or image.dtype != np.uint8:
        raise ValueError("Expected uint8 BGR source image")
    if not isinstance(kernel_size, Integral) or kernel_size < 3 or kernel_size % 2 != 1:
        raise ValueError("Kernel size must be an odd integer >= 3")
    if not isinstance(min_pixels, Integral) or min_pixels < 2:
        raise ValueError("min_pixels must be >= 2")
    h, w = image.shape[:2]
    binary = []
    for mask in masks:
        if mask.shape != (h, w):
            raise ValueError("Mask/source dimensions incompatible")
        if not np.isin(mask, [0, 1, 255]).all():
            raise ValueError("Expected binary mask")
        binary.append(mask != 0)
    occupancy = np.zeros((h, w), dtype=np.int32)
    for mask in binary:
        occupancy += mask
    exclusion = np.zeros((h, w), dtype=bool)
    regions = {}
    for c in candidates or []:
        cid = c["candidate_id"]
        if not cid or cid in regions:
            raise ValueError("Missing/duplicate candidate_id")
        coords = to_merged_bbox(c["bbox"], split_size=(w,h), merged_size=(w,h))
        x1, y1, x2, y2 = coords["bbox"]
        exclusion[y1:y2, x1:x2] = True
        regions[cid] = {"bbox": coords["bbox"], "input_bbox": list(c["bbox"]),
                        "clipped": coords["clipped"], "bbox_area": (x2-x1)*(y2-y1),
                        "center": [(x1+x2)/2, (y1+y2)/2], "intersections": []}
    kernel = np.ones((kernel_size, kernel_size), np.uint8)
    radius = kernel_size // 2
    balloons = []
    for index, mask in enumerate(binary, 1):
        ys, xs = np.nonzero(mask)
        if not len(xs):
            balloons.append({"balloon_id": index, "available": False,
                             "reason": "EMPTY_MASK", "mask_area": 0})
            continue
        bx1, by1, bx2, by2 = int(xs.min()), int(ys.min()), int(xs.max())+1, int(ys.max())+1
        area = int(len(xs))
        inside = cv2.erode(mask.astype(np.uint8), kernel, borderType=cv2.BORDER_CONSTANT,
                           borderValue=0) != 0
        expanded = cv2.dilate(mask.astype(np.uint8), kernel, borderType=cv2.BORDER_CONSTANT,
                              borderValue=0) != 0
        outer = expanded & ~mask
        other = occupancy - mask.astype(np.int32) > 0
        zones = {}
        for name, support in (("INTERIOR", inside), ("INNER_RING", mask & ~inside),
                              ("OUTER_CONTEXT", outer)):
            before = int(np.count_nonzero(support))
            excluded_other = int(np.count_nonzero(support & other)) if name == "OUTER_CONTEXT" else 0
            after_neighbors = support & ~other if name == "OUTER_CONTEXT" else support
            excluded_text = int(np.count_nonzero(after_neighbors & exclusion))
            measured = _stats(image, after_neighbors & ~exclusion, min_pixels)
            measured.update({"geometric_pixel_count": before,
                             "excluded_other_balloon_pixels": excluded_other,
                             "after_other_balloon_exclusion": before-excluded_other,
                             "excluded_ctd_bbox_pixels": excluded_text})
            zones[name] = measured
        differences = {}
        for left, right in (("INTERIOR", "INNER_RING"), ("INTERIOR", "OUTER_CONTEXT"),
                            ("INNER_RING", "OUTER_CONTEXT")):
            ok = zones[left]["available"] and zones[right]["available"]
            differences[f"{left}_MINUS_{right}"] = {
                "available": ok, "reason": None if ok else "ZONE_UNAVAILABLE",
                "metrics": {key: round(value-zones[right]["metrics"][key], 4)
                            for key, value in zones[left]["metrics"].items()} if ok else None}
        related = []
        for cid, region in regions.items():
            x1,y1,x2,y2 = region["bbox"]
            overlap = int(np.count_nonzero(mask[y1:y2, x1:x2]))
            if not overlap:
                continue
            cx,cy = region["center"]
            relation = {"balloon_id": index, "intersection_pixels": overlap,
                        "candidate_inside_percent": round(100*overlap/region["bbox_area"],4),
                        "balloon_occupied_percent": round(100*overlap/area,4),
                        "center_inside_individual_mask": bool(mask[int(cy),int(cx)]),
                        "center_relative_to_mask_bbox": [(cx-bx1)/(bx2-bx1), (cy-by1)/(by2-by1)],
                        "relation": "FULL_CONTAINMENT" if overlap == region["bbox_area"] else "PARTIAL_INTERSECTION"}
            region["intersections"].append(relation)
            related.append(cid)
        balloons.append({"balloon_id": index, "available": True, "reason": None,
                         "mask_area": area, "mask_bbox": [bx1,by1,bx2,by2],
                         "mask_rectangularity": area/((bx2-bx1)*(by2-by1)),
                         "related_candidate_ids": related,
                         "outer_context_clipping": {"left": bx1 < radius, "top": by1 < radius,
                                                    "right": bx2+radius > w, "bottom": by2+radius > h},
                         "zones": zones, "differences": differences})
    for region in regions.values():
        x1,y1,x2,y2 = region["bbox"]
        union_n = int(np.count_nonzero(occupancy[y1:y2,x1:x2]))
        region["union_intersection_pixels"] = union_n
        region["union_inside_percent"] = round(100*union_n/region["bbox_area"],4)
        cx,cy = region["center"]
        region["center_inside_union"] = bool(occupancy[int(cy),int(cx)])
        best = max(region["intersections"], key=lambda r:r["intersection_pixels"], default=None)
        region["best_individual_balloon_id"] = best["balloon_id"] if best else None
        region["available"] = best is not None
        region["reason"] = None if best else "NO_INTERSECTING_BALLOON"
    return {"schema_version": SCHEMA_VERSION, "algorithm": ALGORITHM,
            "parameters": {"kernel_shape": "SQUARE", "kernel_size": int(kernel_size),
                           "morphology_border": "CONSTANT_ZERO", "min_pixels": int(min_pixels),
                           "ctd_exclusion": "ALL_CLIPPED_BBOXES_NO_PADDING",
                           "statistics": "UINT8_OPENCV_HSV_S_GRAY_POPULATION_STD"},
            "ctd_available": candidates is not None, "ctd_count": len(candidates or []),
            "text_exclusion_complete": "UNKNOWN", "image_size": [w,h],
            "balloons": balloons, "candidates": regions}
