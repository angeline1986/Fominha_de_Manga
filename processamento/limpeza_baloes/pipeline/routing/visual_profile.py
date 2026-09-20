"""Nível II-B — visual profile.

Milestone 1A does not classify visual profiles automatically.
"""

from __future__ import annotations

from typing import Any

from ..contracts import MILESTONE_1A_REASON, VISUAL_UNCERTAIN


def classify(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": VISUAL_UNCERTAIN,
        "evidence": {},
        "reason_codes": [MILESTONE_1A_REASON],
    }
