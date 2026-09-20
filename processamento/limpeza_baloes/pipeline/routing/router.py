"""Nível II-C — route selection.

Milestone 1A always routes to REVIEW. This is intentional and fail-closed.
"""

from __future__ import annotations

from typing import Any

from ..contracts import MILESTONE_1A_REASON, ROUTE_REVIEW


def route(
    candidate: dict[str, Any],
    eligibility: dict[str, Any],
    visual_profile: dict[str, Any],
) -> dict[str, Any]:
    return {
        "destination": ROUTE_REVIEW,
        "reason_codes": [MILESTONE_1A_REASON],
    }
