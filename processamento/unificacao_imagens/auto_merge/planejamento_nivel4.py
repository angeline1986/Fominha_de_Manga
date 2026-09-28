"""Plan bounded structural compositions over authoritative Level III residuals."""
import hashlib
from pathlib import Path

import numpy as np
from PIL import Image

from processamento.unificacao_imagens import image_stitcher as v3
from processamento.unificacao_imagens.auto_merge.materializacao_nivel3 import (
    render_source_interval, source_spans,
)
from processamento.unificacao_imagens.auto_merge.nivel3 import read_level3
from processamento.unificacao_imagens.image_stitcher_level4 import (
    DEFAULT_MIN_CHUNK_HEIGHT, estimate_directed_validation_count,
    find_global_safe_composition,
)


def _page_infos(chapter: Path, progress=None) -> tuple[list, int]:
    infos, cursor, width = [], 0, None
    pages = v3.list_pages(chapter)
    for index, path in enumerate(pages, 1):
        with Image.open(path) as image:
            page_width, height = image.size
        if width is not None and page_width != width:
            raise ValueError("Larguras incompatíveis nas imagens-fonte.")
        width = page_width
        infos.append(v3.PageInfo(path, page_width, height, cursor, cursor + height))
        cursor += height
        if progress:
            progress({"stage": "analyze_pages", "current": index,
                      "total": len(pages), "message": f"Validando fonte {index}/{len(pages)}"})
    if not infos:
        raise ValueError("Nenhuma imagem-fonte encontrada.")
    return infos, cursor


def plan_level4(chapter: Path, progress=None) -> dict:
    manga, name = chapter.parent.parent, chapter.name
    directory = manga / "FLUXO_SECUNDARIO" / "01_MERGE_PROCESSAMENTO" / "MERGE_LEVEL3" / name
    manifest = directory / "merge-level3-manifest.json"
    manifest_hash = hashlib.sha256(manifest.read_bytes()).hexdigest()
    level3 = read_level3(manga, name)
    if level3.status != "recorded":
        raise ValueError(level3.error or "Manifesto do Nível III inválido.")
    if hashlib.sha256(manifest.read_bytes()).hexdigest() != manifest_hash:
        raise ValueError("O manifesto do Nível III mudou durante o planejamento.")
    infos, total = _page_infos(chapter, progress)
    if total != level3.data["total_height"]:
        raise ValueError("As imagens-fonte mudaram desde o manifesto do Nível III.")
    parents = level3.data["residuals"]
    estimated = sum(estimate_directed_validation_count(
        item["global_start"], item["global_end"], min_chunk_height=DEFAULT_MIN_CHUNK_HEIGHT,
    ) for item in parents)
    diagnostics, artifacts, residuals, used_names = [], [], [], set()
    completed = 0
    for index, parent in enumerate(parents, 1):
        start, end = parent["global_start"], parent["global_end"]
        image = render_source_interval(chapter, infos, start, end)
        base_done = completed
        result = find_global_safe_composition(
            np.asarray(image.convert("L"), dtype=np.uint8),
            global_start=start, global_end=end,
            progress_callback=lambda current, count: progress({
                "stage": "analyze_residual", "current": base_done + current,
                "total": max(1, estimated),
                "message": f"Analisando residual {index}/{len(parents)} · {current}/{count}",
            }) if progress else None,
        )
        completed += result["evaluated_candidates"]
        diagnostics.append({"segment_id": parent.get("id", index),
                            "global_start": start, "global_end": end,
                            "height": end - start, **result})
        if not result["resolved"]:
            residuals.append({**parent, "global_start": start, "global_end": end,
                              "height": end - start, "status": "failed",
                              "validation": "review_required",
                              "reason": "no_complete_global_safe_composition",
                              "level4_decision": "UNRESOLVED"})
            continue
        for chunk_index, (low, high) in enumerate(zip(result["boundaries"], result["boundaries"][1:]), 1):
            spans = source_spans(infos, low, high)
            name_out = v3.unique_merge_output_name(spans, low, high, used_names)
            artifacts.append({"file": name_out, "global_start": low,
                              "global_end": high, "height": high - low,
                              "width": image.width, "source_spans": spans,
                              "source_segment_id": parent.get("id", index),
                              "source_stage": "level4", "chunk_index": chunk_index})
    if hashlib.sha256(manifest.read_bytes()).hexdigest() != manifest_hash:
        raise ValueError("O manifesto do Nível III mudou durante o planejamento.")
    return {"level3_dir": directory, "level3_sha256": manifest_hash,
            "infos": infos, "total_height": total, "artifacts": artifacts,
            "residuals": residuals, "diagnostics": diagnostics,
            "estimated_candidates": estimated, "evaluated_candidates": completed}
