"""Texto Off pipeline refactor.

Milestone 1A is audit-only: detection + stable contracts + fail-closed routing.
It must not mutate official Texto Off artifacts.
"""

from .contracts import ROUTE_REVIEW, ELIGIBILITY_UNCERTAIN

__all__ = ["ROUTE_REVIEW", "ELIGIBILITY_UNCERTAIN"]
