"""Plan Level V compositions over only the authoritative Level IV residuals."""
import hashlib
from pathlib import Path

import numpy as np
from PIL import Image

from processamento.unificacao_imagens import image_stitcher as v3
from processamento.unificacao_imagens.auto_merge.materializacao_nivel3 import (
    render_source_interval, source_spans,
)
from processamento.unificacao_imagens.auto_merge.nivel4 import read_level4
from processamento.unificacao_imagens.image_stitcher_level5 import (
    DEFAULT_MIN_CHUNK_HEIGHT, find_global_safe_composition,
)


def _page_infos(chapter: Path, progress=None) -> tuple[list, int]:
    infos, cursor, width = [], 0, None
    pages = v3.list_pages(chapter)
    for index, path in enumerate(pages, 1):
        with Image.open(path) as image:
            page_width, height = image.size
        if width is not None and page_width != width:
            raise ValueError("Larguras incompatíveis nas imagens-fonte.")
        width = page_width; infos.append(v3.PageInfo(path, page_width, height, cursor, cursor + height)); cursor += height
        if progress:
            progress({"stage": "analyze_pages", "current": index,
                      "total": len(pages), "message": f"Validando fonte {index}/{len(pages)}"})
    if not infos:
        raise ValueError("Nenhuma imagem-fonte encontrada.")
    return infos, cursor


def plan_level5(chapter: Path, progress=None) -> dict:
    manga, name = chapter.parent.parent, chapter.name
    directory = manga / "FLUXO_SECUNDARIO" / "01_MERGE_PROCESSAMENTO" / "MERGE_LEVEL4" / name
    manifest = directory / "merge-level4-manifest.json"
    source_hash = hashlib.sha256(manifest.read_bytes()).hexdigest()
    level4 = read_level4(manga, name)
    if level4.status != "recorded":
        raise ValueError(level4.error or "Manifesto do Nível IV inválido.")
    if hashlib.sha256(manifest.read_bytes()).hexdigest() != source_hash:
        raise ValueError("O manifesto do Nível IV mudou durante o planejamento.")
    infos, total = _page_infos(chapter, progress)
    if total != level4.data["total_height"]:
        raise ValueError("As imagens-fonte mudaram desde o manifesto do Nível IV.")
    parents = level4.data["residuals"]
    estimated = sum(max(0, item["global_end"] - item["global_start"] - 2 * DEFAULT_MIN_CHUNK_HEIGHT + 1)
                    for item in parents)
    artifacts, residuals, diagnostics, completed = [], [], [], 0
    for index, parent in enumerate(parents, 1):
        start, end = parent["global_start"], parent["global_end"]
        image = render_source_interval(chapter, infos, start, end)
        base_done = completed
        result = find_global_safe_composition(
            np.asarray(image.convert("L"), dtype=np.uint8), global_start=start, global_end=end,
            progress_callback=lambda current, count: progress({
                "stage": "analyze_residual", "current": base_done + current,
                "total": max(1, estimated), "message": f"Busca global SAFE {index}/{len(parents)} · {current}/{count}",
            }) if progress else None,
        )
        completed += int(result.get("evaluated_candidates") or 0)
        diagnostics.append({"segment_id": parent.get("id", index), "global_start": start,
                            "global_end": end, "height": end - start, **result})
        partial = bool(result.get("partial_resolved"))
        if not result.get("resolved") and not partial:
            residuals.append({**parent, "global_start": start, "global_end": end,
                              "height": end - start, "status": "failed",
                              "validation": "review_required", "reason": "no_complete_global_safe_composition",
                              "level5_decision": "UNRESOLVED"})
            continue
        boundaries = [int(value) for value in result.get("boundaries") or []]
        by_y = {int(item["selected_y"]): item for item in result.get("selected_diagnostics") or []
                if item.get("selected_y") is not None}
        for chunk, (low, high) in enumerate(zip(boundaries, boundaries[1:]), 1):
            spans = source_spans(infos, low, high)
            name_out = f"{Path(v3.page_range_output_name_from_spans(spans, low, high)).stem}-l5-{low}-{high}.png"
            artifacts.append({"file": name_out, "global_start": low, "global_end": high,
                              "height": high - low, "width": infos[0].width,
                              "source_spans": spans, "source_stage": "level5",
                              "source_segment_id": parent.get("id", index), "chunk_index": chunk,
                              "decision_reason": (by_y.get(high) or {}).get("reason", "remaining_within_max_height")})
        if partial:
            residual_start = boundaries[-1]
            if not start < residual_start < end:
                raise ValueError("Nível V retornou prefixo SAFE parcial com residual inválido.")
            spans = source_spans(infos, residual_start, end)
            residuals.append({**parent, "global_start": residual_start, "global_end": end,
                              "height": end - residual_start,
                              "sources": [span["file"] for span in spans], "source_spans": spans,
                              "status": "failed", "validation": "review_required",
                              "reason": "partial_safe_prefix_remaining", "level5_decision": "PARTIAL_SAFE"})
    if hashlib.sha256(manifest.read_bytes()).hexdigest() != source_hash:
        raise ValueError("O manifesto do Nível IV mudou durante o planejamento.")
    return {"level4_dir": directory, "level4_sha256": source_hash, "infos": infos,
            "total_height": total, "artifacts": artifacts, "residuals": residuals,
            "diagnostics": diagnostics, "estimated_candidates": estimated,
            "evaluated_candidates": completed}
