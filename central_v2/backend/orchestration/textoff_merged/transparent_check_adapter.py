"""Converte reconhecimento transparente em sugestões para o Check."""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from .consolidated_artifacts import consolidated_image
from .stages import LEVEL1, stage_chapter
from .transparent_recognition import recognize

STAGE = "02_RECONHECER_TRANSPARENTES"
REPORT = "json/transparent-recognition.json"
KIND = "balao_transparente"


def load_suggestions(manga: Path, chapter: str) -> list[dict]:
    """Lê sugestões sem alterar fontes ou decisões do Check."""
    manga = Path(manga)
    path = stage_chapter(
        manga, STAGE, chapter, read_legacy=False
    ) / REPORT

    if not path.is_file():
        return []

    saved = json.loads(path.read_text(encoding="utf-8"))
    current = recognize(stage_chapter(manga, LEVEL1, chapter))

    # Não aceitar sugestões baseadas em fontes que já mudaram.
    if saved != current:
        raise ValueError(
            "Reconhecimento transparente desatualizado ou incompatível."
        )

    result = []
    dimensions = {}

    for candidate in saved["candidates"]:
        page = candidate["source"]
        clean_name = (
            page.removesuffix(".png") + "_clean.png"
        )

        if page not in dimensions:
            image_path = consolidated_image(
                manga, chapter, clean_name
            )
            if image_path is None:
                raise ValueError(
                    f"Imagem consolidada ausente: {page}"
                )
            with Image.open(image_path) as image:
                dimensions[page] = image.size

        width, height = dimensions[page]
        x, y, box_width, box_height = candidate["bbox"]

        if (
            x < 0 or y < 0
            or x + box_width > width
            or y + box_height > height
        ):
            raise ValueError(
                f"Coordenadas incompatíveis: {page}"
            )

        result.append({
            "id": candidate["id"],
            "page": page,
            "origin": "TRANSPARENT_RECOGNITION",
            "origins": ["TRANSPARENT_RECOGNITION"],
            "source_references": [{
                "origin": "TRANSPARENT_RECOGNITION",
                "stage": STAGE,
                "report": REPORT,
                "page": page,
                "balloon": candidate["balloon"],
                "mask_label": candidate["mask_label"],
            }],
            "source_classification": "transparent_balloon",
            "candidate": True,
            "type": KIND,
            "note": None,
            "box": {
                "left": x / width,
                "top": y / height,
                "width": box_width / width,
                "height": box_height / height,
            },
        })

    return result
