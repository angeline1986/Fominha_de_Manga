#!/usr/bin/env python3
"""Auto-Merge Nível IV — composição global conservadora sobre residual do Nível III.

Contrato v1:
- recebe exclusivamente um intervalo residual já validado pelo Nível III;
- reutiliza o classificador estrutural do Nível III sem alterar thresholds;
- aceita apenas candidatos SAFE;
- nunca aceita UNSAFE/INCONCLUSIVE nem força corte;
- procura composição COMPLETA com chunks entre 3000 e 12000 px;
- se não houver composição completa, devolve o intervalo integral como residual.
"""
from __future__ import annotations

from typing import Callable, Any

import numpy as np

from processamento.unificacao_imagens.image_stitcher_level3 import (
    Level3Config,
    Level3Decision,
    Level3PendingRegion,
    analyze_structural_candidate,
)

DEFAULT_TARGET_HEIGHT = 7000
DEFAULT_MIN_CHUNK_HEIGHT = 3000
DEFAULT_MAX_CHUNK_HEIGHT = 12000
DEFAULT_SCAN_STEP = 2


def _path_score(chunks: list[int], target_height: int) -> tuple:
    deviation = sum(abs(int(h) - int(target_height)) for h in chunks)
    imbalance = (max(chunks) - min(chunks)) if chunks else 0
    return (int(deviation), int(imbalance), len(chunks))


def _best_complete_path(
    *,
    start: int,
    end: int,
    safe_positions: list[int],
    min_chunk_height: int,
    max_chunk_height: int,
    target_height: int,
) -> list[int] | None:
    nodes = [int(start)] + sorted(
        {int(y) for y in safe_positions if int(start) < int(y) < int(end)}
    ) + [int(end)]
    best: dict[int, tuple[tuple, list[int], list[int]]] = {
        int(start): ((0, 0, 0), [int(start)], [])
    }
    for y in nodes[1:]:
        chosen = None
        for x in nodes:
            if x >= y:
                break
            previous = best.get(x)
            if previous is None:
                continue
            chunk = int(y) - int(x)
            if chunk < int(min_chunk_height) or chunk > int(max_chunk_height):
                continue
            _, boundaries, chunks = previous
            candidate_chunks = chunks + [chunk]
            candidate_boundaries = boundaries + [int(y)]
            score = _path_score(candidate_chunks, int(target_height))
            candidate = (score, candidate_boundaries, candidate_chunks)
            if chosen is None or (candidate[0], tuple(candidate[1])) < (chosen[0], tuple(chosen[1])):
                chosen = candidate
        if chosen is not None:
            best[int(y)] = chosen
    result = best.get(int(end))
    return list(result[1]) if result is not None else None


def find_global_safe_composition(
    image: np.ndarray,
    *,
    global_start: int,
    global_end: int,
    config: Level3Config | None = None,
    target_height: int = DEFAULT_TARGET_HEIGHT,
    min_chunk_height: int = DEFAULT_MIN_CHUNK_HEIGHT,
    max_chunk_height: int = DEFAULT_MAX_CHUNK_HEIGHT,
    scan_step: int = DEFAULT_SCAN_STEP,
    progress_callback: Callable[[int, int], None] | None = None,
) -> dict[str, Any]:
    start = int(global_start)
    end = int(global_end)
    if end <= start:
        raise ValueError("Intervalo inválido para Auto-Merge Nível IV.")

    min_h = max(1, int(min_chunk_height))
    max_h = max(min_h, int(max_chunk_height))
    target = max(min_h, min(max_h, int(target_height)))
    step = max(1, int(scan_step))
    height = end - start
    region = Level3PendingRegion(start, end)
    cfg = config or Level3Config()

    if height <= max_h:
        return {
            "resolved": True,
            "boundaries": [start, end],
            "cuts": [],
            "chunks": [height],
            "evaluated_candidates": 0,
            "eligible_candidates": 0,
            "safe_candidates": 0,
            "decision_counts": {},
            "reason_counts": {},
            "selected_diagnostics": [],
            "search_passes": 0,
        }

    lower = start + min_h
    upper = end - min_h
    if lower > upper:
        return {
            "resolved": False,
            "boundaries": None,
            "cuts": [],
            "chunks": [],
            "evaluated_candidates": 0,
            "eligible_candidates": 0,
            "safe_candidates": 0,
            "decision_counts": {},
            "reason_counts": {},
            "selected_diagnostics": [],
            "search_passes": 0,
        }

    gray = np.asarray(image, dtype=np.uint8)
    eligible_total = upper - lower + 1
    evaluated = 0
    safe_results: dict[int, Any] = {}
    decision_counts: dict[str, int] = {}
    reason_counts: dict[str, int] = {}

    parities = [0, 1] if step == 2 else [None]
    passes = 0

    for parity in parities:
        passes += 1
        if parity is None:
            positions = range(lower, upper + 1, step)
        else:
            first = lower + ((parity - lower) % 2)
            positions = range(first, upper + 1, 2)

        for y in positions:
            result = analyze_structural_candidate(
                gray,
                candidate_y=int(y),
                region=region,
                image_global_start=start,
                config=cfg,
            )
            evaluated += 1
            decision = result.decision.value
            decision_counts[decision] = decision_counts.get(decision, 0) + 1
            reason_counts[result.reason] = reason_counts.get(result.reason, 0) + 1
            if result.decision == Level3Decision.SAFE:
                safe_results[int(y)] = result
            if progress_callback is not None:
                progress_callback(evaluated, eligible_total)

        boundaries = _best_complete_path(
            start=start,
            end=end,
            safe_positions=list(safe_results),
            min_chunk_height=min_h,
            max_chunk_height=max_h,
            target_height=target,
        )
        if boundaries is not None:
            cuts = boundaries[1:-1]
            chunks = [b - a for a, b in zip(boundaries, boundaries[1:])]
            selected = [
                {**safe_results[int(y)].as_dict(), "selected_y": int(y)}
                for y in cuts
            ]
            return {
                "resolved": True,
                "boundaries": boundaries,
                "cuts": cuts,
                "chunks": chunks,
                "evaluated_candidates": evaluated,
                "eligible_candidates": eligible_total,
                "safe_candidates": len(safe_results),
                "decision_counts": decision_counts,
                "reason_counts": reason_counts,
                "selected_diagnostics": selected,
                "search_passes": passes,
            }

    return {
        "resolved": False,
        "boundaries": None,
        "cuts": [],
        "chunks": [],
        "evaluated_candidates": evaluated,
        "eligible_candidates": eligible_total,
        "safe_candidates": len(safe_results),
        "decision_counts": decision_counts,
        "reason_counts": reason_counts,
        "selected_diagnostics": [],
        "search_passes": passes,
    }
