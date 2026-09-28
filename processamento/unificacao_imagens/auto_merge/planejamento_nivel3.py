"""Plan structural cuts only inside the authoritative Level II residuals."""
import hashlib
from pathlib import Path

import numpy as np
from PIL import Image

from processamento.unificacao_imagens import image_stitcher as v3
from processamento.unificacao_imagens.auto_merge.materializacao_nivel3 import (
    render_source_interval, source_spans,
)
from processamento.unificacao_imagens.auto_merge.nivel2 import read_level2
from processamento.unificacao_imagens.image_stitcher_level3 import (
    Level3Config, Level3Decision, Level3PendingRegion,
    continuous_scene_guard, search_local_safe_candidate,
)


def _page_infos(chapter: Path, callback=None) -> tuple[list, int]:
    pages, infos, cursor, width = v3.list_pages(chapter), [], 0, None
    for index, path in enumerate(pages, start=1):
        with Image.open(path) as image:
            page_width, height = image.size
        if width is not None and page_width != width:
            raise ValueError("Larguras incompatíveis nas imagens-fonte.")
        width = page_width
        infos.append(v3.PageInfo(path, page_width, height, cursor, cursor + height))
        cursor += height
        if callback:
            callback({"stage": "analyze_pages", "current": index,
                      "total": len(pages), "message": f"Validando fonte {index}/{len(pages)}"})
    if not infos:
        raise ValueError("Nenhuma imagem-fonte encontrada.")
    return infos, cursor


def _gray_window(chapter: Path, infos: list, start: int, end: int) -> np.ndarray:
    return np.asarray(render_source_interval(chapter, infos, start, end).convert("L"), dtype=np.uint8)


def _pending(parent: dict, start: int, end: int, infos: list,
             reason: str, result, guard) -> dict:
    spans = source_spans(infos, start, end)
    return {
        "id": int(parent.get("id") or parent.get("index") or 1),
        "global_start": start, "global_end": end, "height": end - start,
        "sources": [item["file"] for item in spans], "source_spans": spans,
        "status": "failed", "validation": "review_required", "reason": reason,
        "level3_decision": result.decision.value,
        "trigger_reason": result.reason, "trigger_decision": result.decision.value,
        "guard_metrics": dict(guard.metrics) if guard else {},
    }


def plan_level3(chapter: Path, progress_callback=None) -> dict:
    manga, name = chapter.parent.parent, chapter.name
    level2_dir = manga / "FLUXO_SECUNDARIO" / "01_MERGE_PROCESSAMENTO" / "MERGE_LEVEL2" / name
    manifest_path = level2_dir / "merge-level2-manifest.json"
    manifest_hash = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    level2 = read_level2(manga, name)
    if level2.status != "recorded":
        raise ValueError(level2.error or "Manifesto do Nível II inválido.")
    if hashlib.sha256(manifest_path.read_bytes()).hexdigest() != manifest_hash:
        raise ValueError("O manifesto do Nível II mudou durante o planejamento.")
    infos, total = _page_infos(chapter, progress_callback)
    if total != level2.data["total_height"]:
        raise ValueError("As imagens-fonte mudaram desde o manifesto do Nível II.")

    config = Level3Config()
    maximum = int(v3.DEFAULT_MAX_CHUNK_HEIGHT)
    parents = level2.data["residuals"]
    estimated = max(1, sum(max(1, (item["global_end"] - item["global_start"] + maximum - 1) // maximum)
                           for item in parents))
    diagnostics, intervals, residuals = [], [], []
    completed = 0
    for index, parent in enumerate(parents, start=1):
        start, end = parent["global_start"], parent["global_end"]
        region = Level3PendingRegion(start, end)
        cursor = start
        while end - cursor > maximum:
            nominal = cursor + maximum
            margin = max(20, int(config.analysis_half_window)) + int(config.local_search_radius)
            window_start = max(start, nominal - margin)
            window_end = min(end, nominal + margin + 1)
            gray = _gray_window(chapter, infos, window_start, window_end)
            result = search_local_safe_candidate(
                gray, candidate_y=nominal, region=region,
                image_global_start=window_start, config=config,
            )
            chosen = None
            if result.decision == Level3Decision.SAFE:
                chosen = int(result.alternative_y if result.alternative_y is not None else result.candidate_y)
            diagnostics.append({**result.as_dict(), "segment_id": index,
                                "nominal_candidate_y": nominal, "selected_y": chosen})
            completed += 1
            if progress_callback:
                progress_callback({"stage": "analyze_residual", "current": completed,
                                   "total": estimated,
                                   "message": f"Analisando residual {index}/{len(parents)}"})
            if chosen is None or chosen <= cursor or chosen >= end:
                guard = continuous_scene_guard(
                    region=Level3PendingRegion(cursor, end), config=config,
                )
                residuals.append(_pending(
                    parent, cursor, end, infos,
                    guard.reason if guard else result.reason, result, guard,
                ))
                break
            intervals.append({"global_start": cursor, "global_end": chosen,
                              "source_segment_id": index,
                              "decision_reason": result.reason})
            cursor = chosen
        else:
            if cursor < end:
                intervals.append({"global_start": cursor, "global_end": end,
                                  "source_segment_id": index,
                                  "decision_reason": "remaining_within_max_height"})
    return {"level2": level2, "level2_dir": level2_dir,
            "level2_sha256": manifest_hash, "infos": infos,
            "total_height": total, "intervals": intervals,
            "residuals": residuals, "diagnostics": diagnostics,
            "config": config}
