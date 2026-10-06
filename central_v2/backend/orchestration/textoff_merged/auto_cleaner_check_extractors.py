"""Read persisted Mapear, Sommelier, and manual occurrence sources."""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from central_v2.backend.orchestration.bubble_sommelier.artifacts import report_path as sommelier_report_path
from .consolidated_artifacts import consolidated_image
from .residue_occurrences import MANIFEST_NAME as RESIDUE_MANIFEST_NAME
from .residue_occurrences import occurrences_for, read_manifest
from .stages import LEVEL3, stage_chapter
from .auto_cleaner_check_geometry import (
    _finite, _mapear_box, _mapear_page_name, _positive_dimension, _source_id,
    _sommelier_box,
)

TYPE_BY_MAPEAR_CLASSIFICATION = {"soft_gradient": "residuo_gradiente"}

def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _mapear_occurrences(manga: Path, chapter: str, pages: dict[str, dict]) -> list[dict]:
    chapter_dir = stage_chapter(manga, LEVEL3, chapter)
    report_path = chapter_dir / "json" / "styled-balloon-report.json"
    report = _read_json(report_path)
    if not isinstance(report, dict) or not isinstance(report.get("pages"), list):
        raise ValueError("Relatório Mapear sem páginas válidas.")
    result = []
    dimension_cache = {}
    for page_record in report["pages"]:
        if not isinstance(page_record, dict):
            continue
        source = page_record.get("source")
        if not isinstance(source, str) or Path(source).name != source:
            continue
        page_name = _mapear_page_name(source)
        if page_name not in pages:
            continue
        candidates = page_record.get("styled_balloon_candidates")
        if not isinstance(candidates, list):
            continue
        if source not in dimension_cache:
            image = consolidated_image(manga, chapter, source)
            if image is None:
                dimension_cache[source] = None
            else:
                with Image.open(image) as source_image:
                    dimension_cache[source] = source_image.size
        dimensions = dimension_cache[source]
        if not dimensions:
            continue
        width, height = dimensions
        for index, candidate in enumerate(candidates):
            if not isinstance(candidate, dict):
                continue
            box = _mapear_box(candidate.get("bbox"), width, height)
            kind = candidate.get("candidate_type")
            if box is None or not isinstance(kind, str) or not kind:
                continue
            detection = candidate.get("detection", index + 1)
            reference = {
                "origin": "MAPEAR", "stage": "TO_MERGED_NIVEL_III",
                "report": "json/styled-balloon-report.json", "page": source,
                "detection": detection, "candidate_type": kind,
            }
            result.append({
                "id": _source_id("mapear", page_name, detection, candidate.get("bbox")),
                "page": page_name, "origin": "MAPEAR", "origins": ["MAPEAR"],
                "source_references": [reference], "source_classification": kind,
                "candidate": True, "type": TYPE_BY_MAPEAR_CLASSIFICATION.get(kind, ""),
                "note": None, "box": box,
            })
    return result


def _sommelier_occurrences(manga: Path, chapter: str, pages: dict[str, dict]) -> list[dict]:
    path = sommelier_report_path(manga, chapter)
    report = _read_json(path)
    if not isinstance(report, dict) or not isinstance(report.get("pages"), list):
        raise ValueError("Relatório Sommelier sem páginas válidas.")
    result = []
    for page_record in report["pages"]:
        if not isinstance(page_record, dict):
            continue
        page_id = page_record.get("page_id")
        page_name = Path(page_id).name if isinstance(page_id, str) else ""
        if page_name not in pages:
            continue
        width, height = page_record.get("width"), page_record.get("height")
        if not _positive_dimension(width) or not _positive_dimension(height):
            continue
        bubbles = page_record.get("bubbles")
        if not isinstance(bubbles, list):
            continue
        for bubble in bubbles:
            if not isinstance(bubble, dict) or bubble.get("candidate") is not True:
                continue
            box = _sommelier_box(bubble.get("bbox"), width, height)
            identity = bubble.get("identity")
            if box is None or not isinstance(identity, str) or not identity:
                continue
            reference = {
                "origin": "SOMMELIER", "stage": "BUBBLE_SOMMELIER",
                "report": "report.json", "page": page_name,
                "identity": identity, "bubble_index": bubble.get("bubble_index"),
                "label": bubble.get("label"), "candidate": True,
            }
            result.append({
                "id": _source_id("sommelier", page_name, identity, bubble.get("bbox")),
                "page": page_name, "origin": "SOMMELIER", "origins": ["SOMMELIER"],
                "source_references": [reference], "source_classification": bubble.get("label"),
                "candidate": True, "type": "", "note": None, "box": box,
            })
    return result


def _manual_occurrences(manga: Path, document: dict, chapter: str,
                        pages: dict[str, dict]) -> list[dict]:
    path = (stage_chapter(manga, "RESIDUE_OCCURRENCES", chapter,
                          read_legacy=False) / RESIDUE_MANIFEST_NAME)
    manifest = read_manifest(path, document)
    result = []
    for page, pair in pages.items():
        for row in occurrences_for(manifest, page, "1"):
            if not isinstance(row, dict) or not isinstance(row.get("box_normalized"), dict):
                continue
            origin = row.get("origin", "MANUAL")
            if origin not in {"MAPEAR", "SOMMELIER", "MANUAL"}:
                origin = "MANUAL"
            source_refs = row.get("source_references")
            if not isinstance(source_refs, list):
                source_refs = [{"origin": origin, "stage": "RESIDUE_OCCURRENCES",
                                "page": page, "step": "1", "id": row.get("id")}]
            result.append({
                "id": row.get("id"), "page": page, "origin": origin,
                "origins": row.get("origins", [origin]),
                "source_references": source_refs,
                "source_classification": row.get("source_classification"),
                "candidate": row.get("candidate"), "type": row.get("tipo", ""),
                "note": row.get("observacao"), "box": dict(row["box_normalized"]),
            })
    return result
