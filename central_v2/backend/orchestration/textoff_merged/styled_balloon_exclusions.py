"""Map earlier transparent detections to the cleaned images used by Mapear."""
from __future__ import annotations

from pathlib import Path


def _clean_image_name(source: str) -> str:
    page = Path(source)
    if page.name != source or page.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
        raise ValueError("Fonte inválida no reconhecimento transparente.")
    return f"{page.stem}_clean{page.suffix}"


def _valid_bbox(value) -> list[int]:
    if (not isinstance(value, list) or len(value) != 4
            or any(type(part) is not int for part in value)
            or value[0] < 0 or value[1] < 0
            or value[2] <= 0 or value[3] <= 0):
        raise ValueError("Caixa inválida no reconhecimento transparente.")
    return value


def regions_by_clean_image(candidates: list[dict], images: list[Path]) -> dict[str, list[list[int]]]:
    """Return prior transparent boxes keyed by the exact Mapear input filename."""
    image_names = {Path(image).name for image in images}
    regions: dict[str, list[list[int]]] = {}
    for candidate in candidates:
        if not isinstance(candidate, dict):
            raise ValueError("Candidato transparente inválido.")
        source = candidate.get("source")
        bbox = _valid_bbox(candidate.get("bbox"))
        if not isinstance(source, str):
            raise ValueError("Fonte inválida no reconhecimento transparente.")
        image_name = _clean_image_name(source)
        if image_name not in image_names:
            raise ValueError(f"Página transparente fora das entradas MAPEAR: {source}")
        regions.setdefault(image_name, []).append(bbox)
    return regions
