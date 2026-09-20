"""Nível I — importação imutável dos candidatos CTD do Panel Cleaner.

Milestone 1A intentionally does not clean, mask, denoise, inpaint or promote.
It consumes Panel Cleaner ``#raw.json`` artifacts produced by the isolated
Text Detection stage and converts every ``blk_list`` entry to a stable Fominha
candidate contract.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .manifests import sha256_file


def _candidate_id(page_key: str, index: int, bbox: list[int]) -> str:
    raw = f"{page_key}|{index}|{','.join(map(str, bbox))}".encode("utf-8")
    return f"ctd-{index:04d}-{hashlib.sha256(raw).hexdigest()[:12]}"


def _normalize_bbox(value: Any) -> list[int]:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        raise ValueError(f"CTD candidate has invalid xyxy: {value!r}")
    bbox = [int(round(float(v))) for v in value]
    x1, y1, x2, y2 = bbox
    if x1 < 0 or y1 < 0 or x2 <= x1 or y2 <= y1:
        raise ValueError(f"CTD candidate has invalid bbox geometry: {bbox!r}")
    return bbox


def _line_count(value: Any) -> int:
    return len(value) if isinstance(value, list) else 0


def import_raw_json(raw_json: Path) -> dict[str, Any]:
    raw_json = Path(raw_json).resolve()
    if not raw_json.is_file():
        raise FileNotFoundError(f"Panel Cleaner raw JSON not found: {raw_json}")
    if not raw_json.name.endswith("#raw.json"):
        raise ValueError("Expected a Panel Cleaner file ending in #raw.json.")

    payload = json.loads(raw_json.read_text(encoding="utf-8"))
    blocks = payload.get("blk_list")
    if not isinstance(blocks, list):
        raise ValueError("Panel Cleaner raw JSON does not contain blk_list.")

    page_key = raw_json.name[:-len("#raw.json")]
    candidates: list[dict[str, Any]] = []

    for index, block in enumerate(blocks, start=1):
        if not isinstance(block, dict):
            raise ValueError(f"CTD candidate #{index} is not an object.")
        bbox = _normalize_bbox(block.get("xyxy"))
        candidate = {
            "candidate_id": _candidate_id(page_key, index, bbox),
            "source_index": index,
            "bbox": bbox,
            "detection": {
                "language": block.get("language"),
                "line_count": _line_count(block.get("lines")),
                "font_size": block.get("font_size"),
                "angle": block.get("angle"),
                "vertical": block.get("vertical"),
                "probability": block.get("prob"),
            },
        }
        candidates.append(candidate)

    return {
        "page_key": page_key,
        "raw_json": raw_json.name,
        "raw_json_sha256": sha256_file(raw_json),
        "image_path": payload.get("image_path"),
        "mask_path": payload.get("mask_path"),
        "original_path": payload.get("original_path"),
        "scale": payload.get("scale"),
        "candidates": candidates,
    }
