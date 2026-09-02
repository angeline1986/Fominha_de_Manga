#!/usr/bin/env python3
"""Auto-Merge Level III structural validator — MIII-1.

This module remains isolated from the productive merge pipeline.

MIII-1 responsibilities:
- preprocess a local image window with light Gaussian blur;
- evaluate structural continuity around a proposed cut;
- detect relevant connected edge masses crossing the cut;
- detect strong diagonal edges crossing the cut;
- treat uniform dark/light regions equally through variance/uniformity;
- return SAFE / UNSAFE / INCONCLUSIVE with auditable metrics.

It intentionally does NOT:
- move the cut (MIII-2);
- detect text/FX (MIII-3);
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
    """Conservative structural thresholds for MIII-1."""

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

    MIII-1 is deliberately conservative:
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

    metrics = {
        "band_std": round(band_std, 6),
        "edge_density": round(edge_density, 6),
        "crossing_components": int(component_count),
        "largest_crossing_component_area": int(largest_component_area),
        "diagonal_crossings": int(diagonal_count),
        "window_top_global": int(image_global_start + top),
        "window_bottom_global": int(image_global_start + bottom),
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
