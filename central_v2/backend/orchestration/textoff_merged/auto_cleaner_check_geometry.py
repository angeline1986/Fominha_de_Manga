"""Geometry normalization and provenance-aware automatic occurrence merging."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from .residue_occurrences import TYPE_LABELS


def _merge_automatic(rows: list[dict], incoming: dict) -> None:
    key = _geometry_key(incoming)
    existing = next((item for item in rows if _geometry_key(item) == key), None)
    if existing is None:
        rows.append(incoming)
        return
    _merge_source_data(existing, incoming)


def _merge_automatic_sources(mapear_rows: list[dict], sommelier_rows: list[dict]) -> list[dict]:
    """Merge exact duplicates, then unique cross-source contained overlaps.

    Containment is the measured relation in the confirmed reports: Mapear's
    segmented-mask rectangle sits inside Sommelier's detection/crop rectangle.
    No distance or IoU threshold is used. Ambiguous overlaps stay separate.
    The Mapear rectangle remains the displayed geometry because it bounds the
    segmented mask; Sommelier contributes its provenance only.
    """
    rows: list[dict] = []
    for item in (*mapear_rows, *sommelier_rows):
        _merge_automatic(rows, item)
    mapear = [(i, row) for i, row in enumerate(rows)
              if row.get("origins") == ["MAPEAR"] and row.get("candidate") is True]
    sommelier = [(i, row) for i, row in enumerate(rows)
                 if row.get("origins") == ["SOMMELIER"] and row.get("candidate") is True]
    overlaps: dict[int, list[int]] = {i: [] for i, _ in mapear}
    som_matches: dict[int, list[int]] = {i: [] for i, _ in sommelier}
    contained_pairs = set()
    for map_index, map_row in mapear:
        for som_index, som_row in sommelier:
            if map_row["page"] != som_row["page"]:
                continue
            if _overlaps(map_row["box"], som_row["box"]):
                overlaps[map_index].append(som_index)
                som_matches[som_index].append(map_index)
                if (_contains(map_row["box"], som_row["box"])
                        or _contains(som_row["box"], map_row["box"])):
                    contained_pairs.add((map_index, som_index))
    merged_sommelier = set()
    for map_index, som_indices in overlaps.items():
        if len(som_indices) != 1:
            continue
        som_index = som_indices[0]
        if len(som_matches[som_index]) == 1 and (map_index, som_index) in contained_pairs:
            _merge_source_data(rows[map_index], rows[som_index])
            merged_sommelier.add(som_index)
    return [row for index, row in enumerate(rows) if index not in merged_sommelier]


def _merge_source_data(existing: dict, incoming: dict) -> None:
    origins = set(existing.get("origins", [existing["origin"]]))
    origins.update(incoming.get("origins", [incoming["origin"]]))
    existing["origins"] = sorted(origins)
    existing["source_references"].extend(incoming.get("source_references", []))
    if existing.get("candidate") is None:
        existing["candidate"] = incoming.get("candidate")
    if not existing.get("type") and incoming.get("type"):
        existing["type"] = incoming["type"]
    classifications = {item.get("origin"): item.get("candidate_type", item.get("label"))
                       for item in existing["source_references"]}
    existing["source_classifications"] = [
        {"origin": origin, "value": value}
        for origin, value in sorted(classifications.items()) if value is not None
    ]


def _contains(outer: dict, inner: dict) -> bool:
    return (outer["left"] <= inner["left"] and outer["top"] <= inner["top"]
            and outer["left"] + outer["width"] >= inner["left"] + inner["width"]
            and outer["top"] + outer["height"] >= inner["top"] + inner["height"])


def _overlaps(left: dict, right: dict) -> bool:
    return (left["left"] < right["left"] + right["width"]
            and right["left"] < left["left"] + left["width"]
            and left["top"] < right["top"] + right["height"]
            and right["top"] < left["top"] + left["height"])


def _to_contract_occurrence(item: dict, number: int, page: str,
                            width: int, height: int) -> dict:
    box = item["box"]
    kind = item.get("type") or None
    result = {
        "id": item["id"], "page": page, "numero": number, "tipo": kind,
        "label": TYPE_LABELS.get(kind), "observacao": item.get("note"),
        "box_normalized": dict(box),
        "box_pixels": {
            "x": round(box["left"] * width), "y": round(box["top"] * height),
            "width": round(box["width"] * width), "height": round(box["height"] * height),
        },
        "origin": item["origin"], "origins": item["origins"],
        "source_references": item.get("source_references", []),
    }
    for name in ("source_classification", "source_classifications", "candidate"):
        if item.get(name) is not None:
            result[name] = item[name]
    return result


def _geometry_key(item: dict) -> tuple:
    return (item["page"], *(round(float(item["box"][key]), 10)
                             for key in ("left", "top", "width", "height")))


def _mapear_box(raw, width: int, height: int) -> dict | None:
    if not isinstance(raw, list) or len(raw) != 4:
        return None
    x, y, box_width, box_height = raw
    if not all(_finite(value) for value in raw) or box_width <= 0 or box_height <= 0:
        return None
    if x < 0 or y < 0 or x + box_width > width or y + box_height > height:
        return None
    return {"left": x / width, "top": y / height,
            "width": box_width / width, "height": box_height / height}


def _sommelier_box(raw, width: int, height: int) -> dict | None:
    if not isinstance(raw, dict):
        return None
    x1, y1, x2, y2 = (raw.get(key) for key in ("x1", "y1", "x2", "y2"))
    if not all(_finite(value) for value in (x1, y1, x2, y2)):
        return None
    if x1 < 0 or y1 < 0 or x2 <= x1 or y2 <= y1 or x2 > width or y2 > height:
        return None
    return {"left": x1 / width, "top": y1 / height,
            "width": (x2 - x1) / width, "height": (y2 - y1) / height}


def _source_id(source: str, page: str, identifier, bbox) -> str:
    encoded = json.dumps([source, page, identifier, bbox], sort_keys=True,
                         separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return f"{source}-{hashlib.sha256(encoded).hexdigest()[:32]}"


def _mapear_page_name(source: str) -> str:
    path = Path(source)
    stem = path.stem[:-6] if path.stem.endswith("_clean") else path.stem
    return f"{stem}{path.suffix}"


def _positive_dimension(value) -> bool:
    return type(value) is int and value > 0


def _finite(value) -> bool:
    return (not isinstance(value, bool) and isinstance(value, (int, float))
            and math.isfinite(value))
