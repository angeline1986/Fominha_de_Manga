#!/usr/bin/env python3
"""Auto-Merge Level III structural validator — MIII-2.

This module remains isolated from the productive merge pipeline.

MIII-2 responsibilities:
- keep MIII-1 structural validation intact;
- search a bounded deterministic neighborhood around an UNSAFE/INCONCLUSIVE cut;
- never force a cut;
- rank only SAFE candidates by structural quality, distance and light upward bias;
- return the original evaluation plus an auditable alternative when one exists.

It intentionally does NOT:
- detect text/FX (MIII-3);
- integrate with Level II/Review (MIII-3);
- write merge artifacts;
- modify Level I, Level II, Review, or final composition.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping

import cv2
import numpy as np


class Level3Decision(str, Enum):
    SAFE = "SAFE"
    UNSAFE = "UNSAFE"
    INCONCLUSIVE = "INCONCLUSIVE"


@dataclass(frozen=True)
class Level3PendingRegion:
    global_start: int
    global_end: int

    @property
    def height(self) -> int:
        return self.global_end - self.global_start

    def contains(self, y: int) -> bool:
        return self.global_start <= int(y) < self.global_end


@dataclass(frozen=True)
class Level3Config:
    """Conservative structural thresholds for Level III."""

    analysis_half_window: int = 120
    cut_band_half_height: int = 8
    gaussian_kernel: int = 5
    canny_low: int = 50
    canny_high: int = 150
    morphology_kernel: int = 3

    # SAFE requires both low local variance and low edge density.
    uniform_std_max: float = 10.0
    safe_edge_density_max: float = 0.015

    # Relevant component crossing the cut.
    min_component_area: int = 24
    min_component_height: int = 10

    # Strong diagonal crossing.
    hough_threshold: int = 18
    hough_min_line_length: int = 24
    hough_max_line_gap: int = 6
    diagonal_min_angle_deg: float = 18.0
    diagonal_max_angle_deg: float = 72.0

    # MIII-2 bounded local search.
    local_search_radius: int = 200
    local_search_step: int = 2

    # MIII-3A text/FX heuristic and long-scene sanity guard.
    text_fx_max_cluster_area: int = 900
    text_fx_max_cluster_width: int = 90
    text_fx_max_cluster_height: int = 60
    text_fx_min_cluster_area: int = 8
    text_fx_min_clusters: int = 3
    text_fx_uniform_background_std_max: float = 18.0
    continuous_scene_max_height: int = 3000


@dataclass(frozen=True)
class Level3Result:
    decision: Level3Decision
    candidate_y: int
    reason: str
    region_start: int
    region_end: int
    metrics: Mapping[str, Any] = field(default_factory=dict)
    alternative_y: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision.value,
            "candidate_y": int(self.candidate_y),
            "reason": str(self.reason),
            "region": {
                "global_start": int(self.region_start),
                "global_end": int(self.region_end),
            },
            "metrics": dict(self.metrics),
            "alternative_y": (
                int(self.alternative_y)
                if self.alternative_y is not None
                else None
            ),
        }


def normalize_pending_segments(
    pending_segments: Iterable[Mapping[str, Any]] | None,
    *,
    total_height: int,
) -> list[Level3PendingRegion]:
    try:
        total = int(total_height)
    except (TypeError, ValueError) as exc:
        raise ValueError("total_height inválido para Level III.") from exc

    if total <= 0:
        raise ValueError("total_height deve ser positivo para Level III.")

    normalized: list[Level3PendingRegion] = []
    for index, raw in enumerate(pending_segments or [], start=1):
        try:
            start = int(raw["global_start"])
            end = int(raw["global_end"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(
                f"Pending segment #{index} possui limites inválidos."
            ) from exc

        if start < 0 or end > total:
            raise ValueError(
                f"Pending segment #{index} está fora da cobertura 0..{total}."
            )
        if end <= start:
            raise ValueError(
                f"Pending segment #{index} possui intervalo vazio/invertido."
            )

        normalized.append(Level3PendingRegion(start, end))

    normalized.sort(key=lambda item: (item.global_start, item.global_end))

    previous_end: int | None = None
    for index, item in enumerate(normalized, start=1):
        if previous_end is not None and item.global_start < previous_end:
            raise ValueError(
                f"Pending segment normalizado #{index} sobrepõe o anterior."
            )
        previous_end = item.global_end

    return normalized


def _ensure_grayscale_uint8(image: np.ndarray) -> np.ndarray:
    if not isinstance(image, np.ndarray):
        raise TypeError("image deve ser um numpy.ndarray.")

    if image.ndim == 2:
        gray = image
    elif image.ndim == 3 and image.shape[2] == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    elif image.ndim == 3 and image.shape[2] == 4:
        gray = cv2.cvtColor(image, cv2.COLOR_BGRA2GRAY)
    else:
        raise ValueError("Formato de imagem não suportado pelo Level III.")

    if gray.dtype != np.uint8:
        gray = np.clip(gray, 0, 255).astype(np.uint8)

    if gray.shape[0] < 3 or gray.shape[1] < 3:
        raise ValueError("Imagem pequena demais para análise estrutural.")

    return gray


def preprocess_for_structure(
    image: np.ndarray,
    *,
    config: Level3Config | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Return lightly denoised grayscale image and Canny edges."""
    cfg = config or Level3Config()
    gray = _ensure_grayscale_uint8(image)

    kernel = int(cfg.gaussian_kernel)
    if kernel < 1:
        kernel = 1
    if kernel % 2 == 0:
        kernel += 1

    blurred = cv2.GaussianBlur(gray, (kernel, kernel), 0)
    edges = cv2.Canny(
        blurred,
        threshold1=int(cfg.canny_low),
        threshold2=int(cfg.canny_high),
    )
    return blurred, edges


def _segment_intersects_cut(y1: int, y2: int, cut_y: int) -> bool:
    return min(y1, y2) <= cut_y <= max(y1, y2)


def _strong_diagonal_crossing(
    edges: np.ndarray,
    *,
    cut_y: int,
    config: Level3Config,
) -> tuple[bool, int]:
    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180.0,
        threshold=int(config.hough_threshold),
        minLineLength=int(config.hough_min_line_length),
        maxLineGap=int(config.hough_max_line_gap),
    )
    if lines is None:
        return False, 0

    count = 0
    for raw in lines[:, 0, :]:
        x1, y1, x2, y2 = map(int, raw)
        if not _segment_intersects_cut(y1, y2, cut_y):
            continue

        dx = x2 - x1
        dy = y2 - y1
        if dx == 0:
            angle = 90.0
        else:
            angle = abs(float(np.degrees(np.arctan2(dy, dx))))
            if angle > 90.0:
                angle = 180.0 - angle

        if (
            float(config.diagonal_min_angle_deg)
            <= angle
            <= float(config.diagonal_max_angle_deg)
        ):
            count += 1

    return count > 0, count


def _crossing_components(
    edges: np.ndarray,
    *,
    cut_y: int,
    config: Level3Config,
) -> tuple[int, int]:
    """Return (relevant_crossing_count, largest_crossing_area)."""
    k = max(1, int(config.morphology_kernel))
    kernel = np.ones((k, k), dtype=np.uint8)
    connected = cv2.dilate(edges, kernel, iterations=1)

    num_labels, _, stats, _ = cv2.connectedComponentsWithStats(
        (connected > 0).astype(np.uint8),
        connectivity=8,
    )

    relevant = 0
    largest_area = 0
    for label in range(1, num_labels):
        x, y, w, h, area = map(int, stats[label])
        del x, w
        if y <= cut_y <= (y + h - 1):
            if (
                area >= int(config.min_component_area)
                and h >= int(config.min_component_height)
            ):
                relevant += 1
                largest_area = max(largest_area, area)

    return relevant, largest_area


def _text_fx_clusters(
    gray_window: np.ndarray,
    edges: np.ndarray,
    *,
    cut_y: int,
    config: Level3Config,
) -> tuple[bool, dict[str, int | float]]:
    """Heurística conservadora para possível texto/FX próximo ao corte.

    Sem OCR e sem IA: procura pequenos agrupamentos de borda relativamente
    densos/isolados em fundo local razoavelmente uniforme. É apenas um sinal de
    proteção; nunca transforma um candidato inseguro em seguro.
    """
    binary = (edges > 0).astype(np.uint8)
    num_labels, _, stats, _ = cv2.connectedComponentsWithStats(
        binary,
        connectivity=8,
    )

    band_half = max(4, int(config.cut_band_half_height) * 2)
    y0 = max(0, cut_y - band_half)
    y1 = min(gray_window.shape[0], cut_y + band_half + 1)
    bg_band = gray_window[y0:y1, :].astype(np.float32, copy=False)
    flat = bg_band.reshape(-1)
    if flat.size:
        lo = float(np.percentile(flat, 10.0))
        hi = float(np.percentile(flat, 90.0))
        core = flat[(flat >= lo) & (flat <= hi)]
        if core.size < max(32, flat.size // 4):
            core = flat
        local_bg_std = float(np.std(core))
    else:
        local_bg_std = 0.0

    eligible = 0
    nearest_distance = gray_window.shape[0]

    for label in range(1, num_labels):
        x, y, w, h, area = map(int, stats[label])
        del x
        if area < int(config.text_fx_min_cluster_area):
            continue
        if area > int(config.text_fx_max_cluster_area):
            continue
        if w > int(config.text_fx_max_cluster_width):
            continue
        if h > int(config.text_fx_max_cluster_height):
            continue

        comp_top = y
        comp_bottom = y + h - 1
        if comp_top <= cut_y <= comp_bottom:
            distance = 0
        else:
            distance = min(abs(cut_y - comp_top), abs(cut_y - comp_bottom))

        if distance <= band_half:
            eligible += 1
            nearest_distance = min(nearest_distance, distance)

    suspected = bool(
        eligible >= int(config.text_fx_min_clusters)
        and local_bg_std <= float(config.text_fx_uniform_background_std_max)
    )
    return suspected, {
        'text_fx_clusters': int(eligible),
        'text_fx_nearest_distance': int(nearest_distance) if eligible else -1,
        'text_fx_background_std': round(local_bg_std, 6),
    }


def continuous_scene_guard(
    *,
    region: Level3PendingRegion,
    config: Level3Config | None = None,
) -> Level3Result | None:
    """Fail closed when a pending continuous region is too long.

    This guard is independent from the merge chunk-height policy. A very long
    unresolved region goes to Review instead of encouraging speculative cuts.
    """
    cfg = config or Level3Config()
    threshold = max(1, int(cfg.continuous_scene_max_height))

    if region.height <= threshold:
        return None

    return Level3Result(
        decision=Level3Decision.INCONCLUSIVE,
        candidate_y=int(region.global_start),
        reason='continuous_scene_too_long',
        region_start=region.global_start,
        region_end=region.global_end,
        metrics={
            'region_height': int(region.height),
            'continuous_scene_max_height': int(threshold),
        },
        alternative_y=None,
    )


def analyze_structural_candidate(
    image: np.ndarray,
    *,
    candidate_y: int,
    region: Level3PendingRegion,
    image_global_start: int = 0,
    config: Level3Config | None = None,
) -> Level3Result:
    """Evaluate one candidate without moving it.

    `candidate_y` is global chapter Y.
    `image_global_start` is the global Y represented by image row 0.

    MIII-1/MIII-2 conservative decision order:
    1. strong diagonal crossing -> UNSAFE;
    2. relevant connected edge mass crossing -> UNSAFE;
    3. uniform low-edge band -> SAFE;
    4. everything else -> INCONCLUSIVE.
    """
    cfg = config or Level3Config()
    global_y = int(candidate_y)

    if not region.contains(global_y):
        raise ValueError(
            "candidate_y precisa estar dentro da região pendente do Level III."
        )

    gray = _ensure_grayscale_uint8(image)
    local_y = global_y - int(image_global_start)
    if local_y < 0 or local_y >= gray.shape[0]:
        raise ValueError("candidate_y não está coberto pela imagem fornecida.")

    half_window = max(20, int(cfg.analysis_half_window))
    top = max(0, local_y - half_window)
    bottom = min(gray.shape[0], local_y + half_window + 1)
    window = gray[top:bottom, :]
    cut_y = local_y - top

    if window.shape[0] < 5:
        raise ValueError("Contexto insuficiente ao redor do candidato.")

    blurred, edges = preprocess_for_structure(window, config=cfg)

    band_half = max(1, int(cfg.cut_band_half_height))
    band_top = max(0, cut_y - band_half)
    band_bottom = min(blurred.shape[0], cut_y + band_half + 1)
    band = blurred[band_top:band_bottom, :]
    edge_band = edges[band_top:band_bottom, :]

    band_std = float(np.std(band))
    edge_density = float(np.count_nonzero(edge_band)) / float(edge_band.size)

    diagonal, diagonal_count = _strong_diagonal_crossing(
        edges,
        cut_y=cut_y,
        config=cfg,
    )
    component_count, largest_component_area = _crossing_components(
        edges,
        cut_y=cut_y,
        config=cfg,
    )

    text_fx, text_fx_metrics = _text_fx_clusters(
        blurred,
        edges,
        cut_y=cut_y,
        config=cfg,
    )

    metrics = {
        "band_std": round(band_std, 6),
        "edge_density": round(edge_density, 6),
        "crossing_components": int(component_count),
        "largest_crossing_component_area": int(largest_component_area),
        "diagonal_crossings": int(diagonal_count),
        "window_top_global": int(image_global_start + top),
        "window_bottom_global": int(image_global_start + bottom),
        **text_fx_metrics,
    }

    if diagonal:
        return Level3Result(
            decision=Level3Decision.UNSAFE,
            candidate_y=global_y,
            reason="strong_diagonal_crossing",
            region_start=region.global_start,
            region_end=region.global_end,
            metrics=metrics,
        )

    if component_count > 0:
        return Level3Result(
            decision=Level3Decision.UNSAFE,
            candidate_y=global_y,
            reason="connected_component_crossing",
            region_start=region.global_start,
            region_end=region.global_end,
            metrics=metrics,
        )

    if text_fx:
        return Level3Result(
            decision=Level3Decision.UNSAFE,
            candidate_y=global_y,
            reason="text_like_region",
            region_start=region.global_start,
            region_end=region.global_end,
            metrics=metrics,
        )

    if (
        band_std <= float(cfg.uniform_std_max)
        and edge_density <= float(cfg.safe_edge_density_max)
    ):
        return Level3Result(
            decision=Level3Decision.SAFE,
            candidate_y=global_y,
            reason="structurally_clear_uniform_band",
            region_start=region.global_start,
            region_end=region.global_end,
            metrics=metrics,
        )

    return Level3Result(
        decision=Level3Decision.INCONCLUSIVE,
        candidate_y=global_y,
        reason="structural_evidence_inconclusive",
        region_start=region.global_start,
        region_end=region.global_end,
        metrics=metrics,
    )


def _candidate_search_bounds(
    *,
    candidate_y: int,
    region: Level3PendingRegion,
    image_global_start: int,
    image_height: int,
    config: Level3Config,
) -> tuple[int, int]:
    radius = max(0, int(config.local_search_radius))
    image_end_exclusive = int(image_global_start) + int(image_height)

    lower = max(
        int(region.global_start),
        int(image_global_start),
        int(candidate_y) - radius,
    )
    upper = min(
        int(region.global_end) - 1,
        image_end_exclusive - 1,
        int(candidate_y) + radius,
    )
    return lower, upper


def _safe_candidate_rank(
    result: Level3Result,
    *,
    original_y: int,
) -> tuple[float, int, int, int]:
    """Lower tuple is better.

    Ranking contract:
    1. lower edge density;
    2. fewer crossing components;
    3. shorter displacement from original;
    4. on a true tie, prefer the slightly earlier/higher cut.

    SAFE candidates normally have zero crossing components already; the field
    remains explicit so the ranking contract stays auditable and extensible.
    """
    edge_density = float(result.metrics.get("edge_density", 1.0))
    components = int(result.metrics.get("crossing_components", 999999))
    delta = int(result.candidate_y) - int(original_y)
    distance = abs(delta)
    upward_tiebreak = 0 if delta < 0 else 1
    return (edge_density, components, distance, upward_tiebreak)


def search_local_safe_candidate(
    image: np.ndarray,
    *,
    candidate_y: int,
    region: Level3PendingRegion,
    image_global_start: int = 0,
    config: Level3Config | None = None,
) -> Level3Result:
    """Evaluate candidate and, if needed, search a bounded SAFE alternative.

    The function never changes a candidate already classified SAFE.
    It never returns an alternative that was not independently classified SAFE.
    It never searches outside:
    - the configured ±radius;
    - the pending Level III region;
    - the supplied image coverage.

    When no SAFE alternative exists, the original decision is preserved and
    alternative_y remains None.
    """
    cfg = config or Level3Config()
    gray = _ensure_grayscale_uint8(image)

    original = analyze_structural_candidate(
        gray,
        candidate_y=int(candidate_y),
        region=region,
        image_global_start=int(image_global_start),
        config=cfg,
    )
    if original.decision != Level3Decision.UNSAFE:
        metrics = dict(original.metrics)
        metrics.update(
            {
                "local_search_performed": False,
                "local_search_radius": int(cfg.local_search_radius),
                "local_search_step": int(cfg.local_search_step),
                "safe_alternatives_found": 0,
            }
        )
        return Level3Result(
            decision=original.decision,
            candidate_y=original.candidate_y,
            reason=original.reason,
            region_start=original.region_start,
            region_end=original.region_end,
            metrics=metrics,
            alternative_y=None,
        )

    lower, upper = _candidate_search_bounds(
        candidate_y=int(candidate_y),
        region=region,
        image_global_start=int(image_global_start),
        image_height=gray.shape[0],
        config=cfg,
    )

    step = max(1, int(cfg.local_search_step))
    safe_results: list[Level3Result] = []
    evaluated = 0

    # Deterministic complete scan. Ranking, not iteration order, chooses winner.
    for y in range(lower, upper + 1, step):
        if y == int(candidate_y):
            continue
        evaluated += 1
        result = analyze_structural_candidate(
            gray,
            candidate_y=y,
            region=region,
            image_global_start=int(image_global_start),
            config=cfg,
        )
        if result.decision == Level3Decision.SAFE:
            safe_results.append(result)

    if not safe_results:
        metrics = dict(original.metrics)
        metrics.update(
            {
                "local_search_performed": True,
                "local_search_lower": int(lower),
                "local_search_upper": int(upper),
                "local_search_radius": int(cfg.local_search_radius),
                "local_search_step": int(step),
                "local_candidates_evaluated": int(evaluated),
                "safe_alternatives_found": 0,
            }
        )
        return Level3Result(
            decision=original.decision,
            candidate_y=original.candidate_y,
            reason=original.reason,
            region_start=original.region_start,
            region_end=original.region_end,
            metrics=metrics,
            alternative_y=None,
        )

    best = min(
        safe_results,
        key=lambda item: _safe_candidate_rank(
            item,
            original_y=int(candidate_y),
        ),
    )

    metrics = dict(original.metrics)
    metrics.update(
        {
            "local_search_performed": True,
            "local_search_lower": int(lower),
            "local_search_upper": int(upper),
            "local_search_radius": int(cfg.local_search_radius),
            "local_search_step": int(step),
            "local_candidates_evaluated": int(evaluated),
            "safe_alternatives_found": int(len(safe_results)),
            "selected_edge_density": float(
                best.metrics.get("edge_density", 0.0)
            ),
            "selected_crossing_components": int(
                best.metrics.get("crossing_components", 0)
            ),
            "selected_distance": abs(
                int(best.candidate_y) - int(candidate_y)
            ),
            "selected_direction": (
                "up"
                if int(best.candidate_y) < int(candidate_y)
                else "down"
            ),
        }
    )

    return Level3Result(
        decision=Level3Decision.SAFE,
        candidate_y=int(candidate_y),
        reason="local_candidate_safe",
        region_start=region.global_start,
        region_end=region.global_end,
        metrics=metrics,
        alternative_y=int(best.candidate_y),
    )


def placeholder_structural_evaluation(
    *,
    candidate_y: int,
    region: Level3PendingRegion,
) -> Level3Result:
    """Compatibility helper kept fail-closed for callers from MIII-0 tests."""
    y = int(candidate_y)
    if not region.contains(y):
        raise ValueError(
            "candidate_y precisa estar dentro da região pendente do Level III."
        )

    return Level3Result(
        decision=Level3Decision.INCONCLUSIVE,
        candidate_y=y,
        reason="structural_analysis_not_implemented",
        region_start=region.global_start,
        region_end=region.global_end,
        metrics={},
        alternative_y=None,
    )
