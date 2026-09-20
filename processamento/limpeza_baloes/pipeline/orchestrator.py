"""Audit-only orchestrator for Texto Off pipeline Milestones 1A/1B/1C."""

from __future__ import annotations

import argparse
import copy
from pathlib import Path
from typing import Any

from .balloon_evidence import analyze_page
from .contracts import (
    ELIGIBILITY_PROTECT,
    ELIGIBILITY_REMOVE,
    ELIGIBILITY_UNCERTAIN,
    PIPELINE_ALGORITHM,
    ROUTE_LEVEL_3,
    ROUTE_LEVEL_4,
    ROUTE_LEVEL_5,
    ROUTE_PROTECT,
    ROUTE_REVIEW,
    SCHEMA_VERSION,
)
from .detection import import_raw_json
from .manifests import write_json_atomic, sha256_file
from .visual_evidence import analyze_page as analyze_visual_page
from .routing.eligibility import evaluate
from .routing.router import route
from .routing.visual_profile import classify


def build_audit(raw_json: Path) -> dict[str, Any]:
    raw_json = Path(raw_json).resolve()
    detected = import_raw_json(raw_json)

    balloon = analyze_page(
        raw_json,
        detected.get("original_path"),
        detected.get("image_path"),
        detected["candidates"],
    )

    visual_evidence = analyze_visual_page(
        Path(balloon["source_image"]),
        detected["candidates"],
    )

    routed: list[dict[str, Any]] = []
    for source_candidate in detected["candidates"]:
        candidate = copy.deepcopy(source_candidate)
        candidate["balloon_evidence"] = balloon["candidates"][candidate["candidate_id"]]
        candidate["visual_evidence"] = visual_evidence["candidates"][candidate["candidate_id"]]

        # Milestone 1C still makes no automatic semantic or visual decision.
        eligibility = evaluate(candidate)
        visual = classify(candidate)
        routing = route(candidate, eligibility, visual)
        candidate["eligibility"] = eligibility
        candidate["visual_profile"] = visual
        candidate["routing"] = routing
        routed.append(candidate)

    eligibility_counts = {
        ELIGIBILITY_REMOVE: 0,
        ELIGIBILITY_PROTECT: 0,
        ELIGIBILITY_UNCERTAIN: 0,
    }
    route_counts = {
        ROUTE_PROTECT: 0,
        ROUTE_REVIEW: 0,
        ROUTE_LEVEL_3: 0,
        ROUTE_LEVEL_4: 0,
        ROUTE_LEVEL_5: 0,
    }
    for candidate in routed:
        eligibility_counts[candidate["eligibility"]["decision"]] += 1
        route_counts[candidate["routing"]["destination"]] += 1

    return {
        "schema_version": SCHEMA_VERSION,
        "algorithm": PIPELINE_ALGORITHM,
        "milestone": "1C",
        "mode": "AUDIT_ONLY",
        "source": {
            "page_key": detected["page_key"],
            "raw_json": detected["raw_json"],
            "raw_json_sha256": detected["raw_json_sha256"],
            "image_path": detected["image_path"],
            "original_path": detected["original_path"],
            "resolved_source_image": balloon["source_image"],
            "scale": detected["scale"],
        },
        "balloon_detection": {
            "balloons_detected": balloon["balloons_detected"],
            "image_width": balloon["image_width"],
            "image_height": balloon["image_height"],
            "model": balloon["model"],
        },
        "region_evidence": balloon["region_evidence"],
        "level1": {
            "candidates_detected": len(routed),
            "candidates": routed,
        },
        "level2": {
            "eligibility_counts": eligibility_counts,
            "routing_counts": route_counts,
        },
        "safety": {
            "official_artifacts_modified": False,
            "cleaner_v2_modified": False,
            "legacy_level1_modified": False,
            "legacy_level2_modified": False,
            "legacy_level3_modified": False,
            "pixel_mutation_performed": False,
            "automatic_cleaning_enabled": False,
            "automatic_eligibility_enabled": False,
            "automatic_visual_classification_enabled": False,
            "fail_closed": True,
        },
    }


def build_merged_audit(source_image: Path, split_sources: list[dict[str, Any]]) -> dict[str, Any]:
    """M2 in memory, with one YOLO segmentation of the immutable MERGED source.

split_sources entries contain raw_json and offset=[x,y] in MERGED pixels.
The original split must equal the corresponding source crop byte-for-byte after
decoding. No inferred offsets, fixture labels or semantic cross-split grouping.
Existing visual_evidence is still measured around CTD boxes on its original
sampling image, not relabeled as balloon interior or substituted by M2 zones.
No Cleaner masks are opened and no reports or images are written here.
"""
    import cv2
    import numpy as np
    from .balloon_evidence import _resolve_source_path
    from .region_evidence import to_merged_bbox

    source_image = Path(source_image).resolve()
    source_hash = sha256_file(source_image)
    image = cv2.imread(str(source_image))
    if image is None:
        raise ValueError("Cannot read MERGED source")
    mh, mw = image.shape[:2]
    candidates = []
    local_visual = {}
    origins = []
    seen = set()
    if not split_sources:
        raise ValueError("Explicit split sources required")
    for entry in split_sources:
        raw = Path(entry["raw_json"]).resolve()
        detected = import_raw_json(raw)
        original_path = _resolve_source_path(raw, detected.get("original_path"), None)
        split_hash = sha256_file(original_path)
        split_image = cv2.imread(str(original_path))
        if split_image is None:
            raise ValueError("Cannot read original split")
        sh, sw = split_image.shape[:2]
        offset = entry["offset"]
        scale = float(detected["scale"])
        # Validate dimensions/offset/scale even for an empty candidate list.
        to_merged_bbox([0,0,sw*scale,sh*scale], split_size=(sw,sh),
                       merged_size=(mw,mh), offset=offset, scale=scale)
        ox, oy = offset
        if not np.array_equal(split_image, image[oy:oy+sh, ox:ox+sw]):
            raise ValueError("Split pixels do not match MERGED source")
        sampling_path = original_path
        if scale != 1.0:
            sampling_path = _resolve_source_path(raw, None, detected.get("image_path"))
            sampling = cv2.imread(str(sampling_path))
            if sampling is None or sampling.shape[:2] != (round(sh*scale), round(sw*scale)):
                raise ValueError("CTD scale and image dimensions incompatible")
        visual = analyze_visual_page(sampling_path, detected["candidates"])
        origin = {"raw_json": raw.name, "raw_json_sha256": detected["raw_json_sha256"],
                  "split_page": original_path.name, "split_sha256": split_hash,
                  "offset": list(offset), "scale": scale, "split_size": [sw,sh],
                  "visual_sampling_image_sha256": sha256_file(sampling_path)}
        origins.append(origin)
        for c in detected["candidates"]:
            cid = c["candidate_id"]
            if cid in seen:
                raise ValueError("Duplicate CTD candidate identity")
            seen.add(cid)
            coordinates = to_merged_bbox(c["bbox"], split_size=(sw,sh), merged_size=(mw,mh),
                                         offset=offset, scale=scale)
            candidate = copy.deepcopy(c)
            candidate["bbox"] = coordinates["bbox"]
            candidate["coordinates"] = {**coordinates, "merged_page": source_image.name,
                                         "split_page": original_path.name,
                                         "raw_json": raw.name}
            candidates.append(candidate)
            local_visual[cid] = visual["candidates"][cid]
        if sha256_file(original_path) != split_hash or sha256_file(raw) != detected["raw_json_sha256"]:
            raise ValueError("Source changed during evidence extraction")
    balloon = analyze_page(source_image, str(source_image), None, candidates)
    for candidate in candidates:
        cid = candidate["candidate_id"]
        candidate["balloon_evidence"] = balloon["candidates"][cid]
        candidate["visual_evidence"] = local_visual[cid]
        candidate["eligibility"] = evaluate(candidate)
        candidate["visual_profile"] = classify(candidate)
        candidate["routing"] = route(candidate, candidate["eligibility"], candidate["visual_profile"])
    if sha256_file(source_image) != source_hash:
        raise ValueError("MERGED source changed during evidence extraction")
    return {"schema_version": SCHEMA_VERSION, "algorithm": "textoff_merged_evidence_m2_v1",
            "milestone": "M2", "mode": "AUDIT_ONLY",
            "source": {"page": source_image.name, "sha256": source_hash,
                       "width": mw, "height": mh, "splits": origins},
            "level1": {"candidates_detected": len(candidates), "candidates": candidates},
            "region_evidence": balloon["region_evidence"], "model": balloon["model"],
            "safety": {"pixel_mutation_performed": False, "official_artifacts_modified": False,
                       "automatic_classification_enabled": False, "fail_closed": True,
                       "cleaner_evidence_used": False}}


def run(raw_json: Path, report: Path) -> dict[str, Any]:
    payload = build_audit(raw_json)
    write_json_atomic(report, payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Texto Off pipeline Milestone 1C — CTD + balloon + visual evidence audit, "
            "no pixel mutation and no automatic eligibility."
        )
    )
    parser.add_argument("--raw-json", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()

    payload = run(args.raw_json, args.report)
    print(
        "Texto Off Pipeline 1C: "
        f"{payload['level1']['candidates_detected']} candidato(s); "
        f"{payload['balloon_detection']['balloons_detected']} balão(ões); "
        f"{payload['level2']['routing_counts'][ROUTE_REVIEW]} em REVIEW; "
        "nenhum artefato oficial alterado."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
