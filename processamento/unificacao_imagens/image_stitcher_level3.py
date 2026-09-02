#!/usr/bin/env python3
"""Auto-Merge Level III contract.

MIII-0 intentionally introduces only the isolated contract for the future
structural validator. It does not integrate with Level I, Level II, Review,
official MERGE output, or the web flow.

Safety principles:
- only Level II FAILED/pending intervals are eligible inputs;
- already resolved/PASSED intervals are outside this module's responsibility;
- absence of structural analysis can never produce SAFE;
- no image or merge artifact is created by this module.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping


class Level3Decision(str, Enum):
    """Formal decision contract for Auto-Merge Level III."""

    SAFE = "SAFE"
    UNSAFE = "UNSAFE"
    INCONCLUSIVE = "INCONCLUSIVE"


@dataclass(frozen=True)
class Level3PendingRegion:
    """Normalized Level II pending interval accepted by Level III."""

    global_start: int
    global_end: int

    @property
    def height(self) -> int:
        return self.global_end - self.global_start

    def contains(self, y: int) -> bool:
        return self.global_start <= int(y) < self.global_end


@dataclass(frozen=True)
class Level3Result:
    """Auditable result returned by every future structural evaluation."""

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
    """Validate and normalize Level II pending intervals.

    The contract is deliberately strict:
    - total_height must be positive;
    - intervals must be non-empty and inside source coverage;
    - intervals must not overlap;
    - input order does not matter.

    This function does not infer, merge, expand, or repair intervals.
    """
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


def placeholder_structural_evaluation(
    *,
    candidate_y: int,
    region: Level3PendingRegion,
) -> Level3Result:
    """Safe MIII-0 placeholder.

    Until MIII-1 implements OpenCV structural analysis, Level III must never
    classify a candidate as SAFE. Returning INCONCLUSIVE guarantees that an
    accidental future integration cannot silently approve a cut.
    """
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
