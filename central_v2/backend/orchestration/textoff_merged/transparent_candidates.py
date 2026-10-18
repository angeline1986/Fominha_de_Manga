"""Extrai candidatos transparentes do relatório validado do Nível I."""
from __future__ import annotations

import hashlib
import json


def extract_candidates(report: dict) -> list[dict]:
    if report.get("algorithm") != "textoff_level1_balloon_transparency_gate_v4":
        raise ValueError("Algoritmo do Nível I incompatível.")

    pages = report.get("pages")
    if not isinstance(pages, list):
        raise ValueError("Relatório sem páginas válidas.")

    result = []
    seen = set()

    for page in pages:
        if not isinstance(page, dict):
            raise ValueError("Página inválida no relatório.")

        source = page.get("source")
        if not isinstance(source, str) or not source or "/" in source or "\\" in source:
            raise ValueError("Identificador de página inválido.")

        for balloon in page.get("transparent_balloons", []):
            if not isinstance(balloon, dict):
                raise ValueError("Balão transparente inválido.")

            bbox = balloon.get("bbox")
            label = balloon.get("mask_label")
            number = balloon.get("balloon")

            if (
                not isinstance(bbox, list)
                or len(bbox) != 4
                or not all(type(v) is int for v in bbox)
                or min(bbox[:2]) < 0
                or min(bbox[2:]) <= 0
                or type(label) is not int
                or label <= 0
                or type(number) is not int
                or number <= 0
            ):
                raise ValueError(f"Geometria ou máscara inválida: {source}")

            identity = (source, number)
            if identity in seen:
                raise ValueError(f"Balão duplicado: {identity}")
            seen.add(identity)

            raw_id = json.dumps(
                [source, number, bbox],
                separators=(",", ":"),
                ensure_ascii=False,
            )
            identifier = hashlib.sha256(raw_id.encode("utf-8")).hexdigest()[:24]

            result.append({
                "id": f"transparent-{identifier}",
                "source": source,
                "balloon": number,
                "bbox": bbox,
                "mask_label": label,
                "classification": "transparent_balloon",
                "reason": balloon.get("reason"),
                "origin": "LEVEL1",
            })

    return result
