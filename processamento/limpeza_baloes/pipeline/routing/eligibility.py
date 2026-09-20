"""Nível II-A — eligibility.

Milestone 1A is deliberately fail-closed. No automatic eligibility classifier
is enabled yet; evidence fields are introduced in later milestones.
"""

from __future__ import annotations

from typing import Any

from ..contracts import ELIGIBILITY_UNCERTAIN, MILESTONE_1A_REASON


def evaluate(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "decision": ELIGIBILITY_UNCERTAIN,
        "evidence": {},
        "reason_codes": [MILESTONE_1A_REASON],
    }
