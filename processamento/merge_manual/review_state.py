from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

from PIL import Image

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}


def natural_key(value: str | Path) -> list[Any]:
    name = value.name if isinstance(value, Path) else str(value)
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", name)]


def _is_source_image(path: Path) -> bool:
    return (
        path.is_file()
        and path.suffix.lower() in IMAGE_EXTS
        and not path.stem.lower().endswith("_old")
        and path.name.lower().startswith("page-")
    )


def source_page_spans(chapter_dir: Path) -> list[dict[str, Any]]:
    """Mapeia IMG/<cap> para o mesmo eixo Y global usado pelo merge.

    O contrato é half-open: [global_start, global_end).
    """
    pages = sorted((p for p in chapter_dir.iterdir() if _is_source_image(p)), key=natural_key)
    spans: list[dict[str, Any]] = []
    cursor = 0
    expected_width: int | None = None

    for index, page in enumerate(pages):
        try:
            with Image.open(page) as image:
                width = int(image.width)
                height = int(image.height)
        except Exception as exc:
            raise ValueError(f"Imagem fonte ilegível: {page.name}: {exc}") from exc

        if width <= 0 or height <= 0:
            raise ValueError(f"Imagem fonte possui dimensões inválidas: {page.name}.")
        if expected_width is None:
            expected_width = width
        elif width != expected_width:
            raise ValueError(
                f"Larguras incompatíveis no capítulo: {page.name} possui {width}px; esperado {expected_width}px."
            )

        spans.append(
            {
                "file": page.name,
                "index": index,
                "width": width,
                "height": height,
                "global_start": cursor,
                "global_end": cursor + height,
            }
        )
        cursor += height

    return spans


def _segment_bounds(segment: dict[str, Any]) -> tuple[int, int]:
    try:
        start = int(segment["global_start"])
        end = int(segment["global_end"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Residual de Review sem global_start/global_end válidos.") from exc
    if end <= start:
        raise ValueError(f"Residual de Review inválido: [{start}, {end}).")
    return start, end


def build_pending_blocks(
    chapter_dir: Path,
    pending_segments: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    spans = source_page_spans(chapter_dir)
    if not spans:
        raise ValueError("Capítulo sem imagens page-* elegíveis em IMG.")

    blocks: list[dict[str, Any]] = []
    normalized = sorted((_segment_bounds(seg) for seg in pending_segments), key=lambda item: (item[0], item[1]))

    previous_end: int | None = None
    for block_index, (start, end) in enumerate(normalized, 1):
        if previous_end is not None and start < previous_end:
            raise ValueError("Pendências autoritativas da Revisão Merge possuem OVERLAP.")
        previous_end = end

        pages = []
        for span in spans:
            lo = max(start, int(span["global_start"]))
            hi = min(end, int(span["global_end"]))
            if hi <= lo:
                continue
            pages.append(
                {
                    **span,
                    "pending_start": lo,
                    "pending_end": hi,
                    "pending_height": hi - lo,
                    "source_y_start": lo - int(span["global_start"]),
                    "source_y_end": hi - int(span["global_start"]),
                }
            )

        if not pages:
            raise ValueError(
                f"Residual [{start}, {end}) não intersecta nenhuma imagem fonte atual do capítulo."
            )

        blocks.append(
            {
                "id": f"pending-{block_index}",
                "index": block_index,
                "global_start": start,
                "global_end": end,
                "height": end - start,
                "page_count": len(pages),
                "first_page": pages[0]["file"],
                "last_page": pages[-1]["file"],
                "pages": pages,
            }
        )

    return blocks


def validate_page_range(block: dict[str, Any], start_file: str, end_file: str) -> dict[str, Any]:
    pages = list(block.get("pages") or [])
    by_name = {str(item.get("file")): item for item in pages}
    if start_file not in by_name or end_file not in by_name:
        raise ValueError("Início e fim devem pertencer ao mesmo bloco pendente da Revisão Merge.")

    start_index = next(i for i, item in enumerate(pages) if item["file"] == start_file)
    end_index = next(i for i, item in enumerate(pages) if item["file"] == end_file)
    if end_index < start_index:
        raise ValueError("Fim deve ser igual ou posterior ao início.")

    selected = pages[start_index : end_index + 1]
    global_start = max(int(block["global_start"]), int(selected[0]["global_start"]))
    global_end = min(int(block["global_end"]), int(selected[-1]["global_end"]))
    if global_end <= global_start:
        raise ValueError("Faixa selecionada não possui cobertura válida.")

    return {
        "block_id": block["id"],
        "start_file": start_file,
        "end_file": end_file,
        "page_count": len(selected),
        "files": [item["file"] for item in selected],
        "global_start": global_start,
        "global_end": global_end,
        "height": global_end - global_start,
    }


def state_from_review_row(review_row: dict[str, Any]) -> dict[str, Any]:
    """Converte o MESMO estado já calculado para Revisão Merge em estado do Merge Manual.

    Não recalcula Level I-V e não importa módulos de Auto-Merge. O host entrega o
    `row_state()` já usado pela Central; este módulo apenas lê o resultado.
    """
    needs_review = bool(review_row.get("needs_review"))
    merge_state = str(review_row.get("merge_state") or "")

    if not needs_review and merge_state != "pendente_review":
        return {"eligible": False, "status": "outside_review", "source": None, "error": None, "pending_segments": []}

    level5 = review_row.get("merge_level5_detail") or {}
    if bool(level5.get("available")):
        if not bool(level5.get("valid")):
            return {
                "eligible": True,
                "status": "blocked",
                "source": "level5",
                "error": str(level5.get("error") or "Estado Level V inválido para a Revisão Merge."),
                "pending_segments": [],
            }
        pending = list(level5.get("review_pending_segments") or [])
        return {
            "eligible": True,
            "status": "pending" if pending else "resolved",
            "source": "level5",
            "error": None,
            "pending_segments": pending,
        }

    level4 = review_row.get("merge_level4_detail") or {}
    algorithm = str(level4.get("algorithm") or "")
    if algorithm == "merge_level4_global_structural_safe_v1" and bool(level4.get("valid")):
        pending = list(level4.get("review_pending_segments") or level4.get("residual_pending_segments") or [])
        return {
            "eligible": True,
            "status": "pending" if pending else "resolved",
            "source": "legacy_level4",
            "error": None,
            "pending_segments": pending,
        }

    return {
        "eligible": True,
        "status": "blocked",
        "source": "review",
        "error": "A Revisão Merge marcou o capítulo como pendente, mas não expôs residual autoritativo elegível ao Merge Manual.",
        "pending_segments": [],
    }
