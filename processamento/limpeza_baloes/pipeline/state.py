"""Milestone 2C.1 — estado/progressão audit-only do pipeline Texto Off.

Este módulo não altera pixels, não executa Cleaner/LaMa e não promove artefatos.
A autoridade é por região; o estado de página é sempre derivado das regiões.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from .contracts import (
    ROUTE_LEVEL_3,
    ROUTE_LEVEL_4,
    ROUTE_LEVEL_5,
    ROUTE_PROTECT,
    ROUTE_REVIEW,
)
from .manifests import sha256_file

STATE_SCHEMA_VERSION = 1

STATUS_PENDING = "PENDING"
STATUS_RESOLVED = "RESOLVED"
STATUS_PROTECTED = "PROTECTED"
STATUS_REVIEW = "REVIEW"

VALID_STATUSES = {
    STATUS_PENDING,
    STATUS_RESOLVED,
    STATUS_PROTECTED,
    STATUS_REVIEW,
}

LEVEL_ROUTES = {ROUTE_LEVEL_3, ROUTE_LEVEL_4, ROUTE_LEVEL_5}


def initial_status_for_route(route: str) -> str:
    if route in LEVEL_ROUTES:
        return STATUS_PENDING
    if route == ROUTE_PROTECT:
        return STATUS_PROTECTED
    if route == ROUTE_REVIEW:
        return STATUS_REVIEW
    raise ValueError(f"Unsupported Text Off route: {route!r}")


def build_page_state(audit: dict[str, Any], source_image: Path) -> dict[str, Any]:
    """Materializa estado inicial a partir do contrato real de build_audit().

    Não decide eligibility/profile/route; apenas preserva as decisões existentes.
    """
    source_image = Path(source_image).resolve()
    if not source_image.is_file():
        raise FileNotFoundError(f"Text Off source image not found: {source_image}")

    source = audit.get("source")
    level1 = audit.get("level1")
    if not isinstance(source, dict):
        raise ValueError("Audit is missing source identity.")
    if not isinstance(level1, dict):
        raise ValueError("Audit is missing level1.")

    page_key = str(source.get("page_key") or "")
    raw_json = str(source.get("raw_json") or "")
    raw_sha = str(source.get("raw_json_sha256") or "")
    candidates = level1.get("candidates")

    if not page_key or not raw_json or not raw_sha:
        raise ValueError("Audit is missing page/source identity.")
    if not isinstance(candidates, list):
        raise ValueError("Audit level1 candidates must be a list.")

    regions = []
    seen = set()
    for candidate in candidates:
        candidate_id = str(candidate.get("candidate_id") or "")
        if not candidate_id or candidate_id in seen:
            raise ValueError(f"Invalid/duplicate candidate_id: {candidate_id!r}")
        seen.add(candidate_id)

        routing = candidate.get("routing")
        if not isinstance(routing, dict):
            raise ValueError(f"Candidate {candidate_id!r} is missing routing.")
        route = routing.get("destination")

        eligibility = candidate.get("eligibility")
        visual_profile = candidate.get("visual_profile")
        region = {
            "candidate_id": candidate_id,
            "source_index": candidate.get("source_index"),
            "bbox": deepcopy(candidate.get("bbox")),
            "eligibility": deepcopy(eligibility),
            "visual_profile": deepcopy(visual_profile),
            "route": route,
            "status": initial_status_for_route(route),
            "resolved_by": None,
            "reason_codes": deepcopy(routing.get("reason_codes") or []),
        }
        regions.append(region)

    state = {
        "schema_version": STATE_SCHEMA_VERSION,
        "page_key": page_key,
        "source": {
            "raw_json": raw_json,
            "raw_json_sha256": raw_sha,
            "source_image": str(source_image),
            "source_image_sha256": sha256_file(source_image),
        },
        "regions": regions,
    }
    validate_page_state(state)
    return state


def validate_page_state(state: dict[str, Any]) -> None:
    if state.get("schema_version") != STATE_SCHEMA_VERSION:
        raise ValueError("Unsupported Text Off pipeline state schema.")
    if not state.get("page_key"):
        raise ValueError("State is missing page_key.")

    source = state.get("source")
    if not isinstance(source, dict):
        raise ValueError("State is missing source identity.")
    for key in ("raw_json", "raw_json_sha256", "source_image", "source_image_sha256"):
        if not source.get(key):
            raise ValueError(f"State source is missing {key}.")

    regions = state.get("regions")
    if not isinstance(regions, list):
        raise ValueError("State regions must be a list.")

    seen = set()
    for region in regions:
        candidate_id = region.get("candidate_id")
        if not candidate_id or candidate_id in seen:
            raise ValueError(f"Invalid/duplicate candidate_id: {candidate_id!r}")
        seen.add(candidate_id)

        route = region.get("route")
        status = region.get("status")
        if status not in VALID_STATUSES:
            raise ValueError(f"Invalid region status: {status!r}")

        if route in LEVEL_ROUTES and status not in {STATUS_PENDING, STATUS_RESOLVED}:
            raise ValueError(f"{route} region cannot have status {status}.")
        if route == ROUTE_PROTECT and status != STATUS_PROTECTED:
            raise ValueError("PROTEGER region must be PROTECTED.")
        if route == ROUTE_REVIEW and status != STATUS_REVIEW:
            raise ValueError("REVIEW region must remain REVIEW.")
        if route not in LEVEL_ROUTES | {ROUTE_PROTECT, ROUTE_REVIEW}:
            raise ValueError(f"Unsupported Text Off route: {route!r}")


def assert_current_sources(
    state: dict[str, Any],
    *,
    raw_json: Path,
    source_image: Path,
) -> None:
    """Fail-closed contra estado produzido por fonte obsoleta."""
    validate_page_state(state)
    raw_json = Path(raw_json).resolve()
    source_image = Path(source_image).resolve()
    source = state["source"]

    if not raw_json.is_file() or not source_image.is_file():
        raise RuntimeError("STALE_STATE: source artifact is missing.")
    if raw_json.name != source["raw_json"]:
        raise RuntimeError("STALE_STATE: raw JSON identity changed.")
    if sha256_file(raw_json) != source["raw_json_sha256"]:
        raise RuntimeError("STALE_STATE: raw JSON changed.")
    if sha256_file(source_image) != source["source_image_sha256"]:
        raise RuntimeError("STALE_STATE: source image changed.")


def page_progress(state: dict[str, Any]) -> dict[str, bool]:
    """Projeta filas por página sem criar uma segunda autoridade de estado."""
    validate_page_state(state)
    regions = state["regions"]

    def pending(route: str) -> bool:
        return any(
            r["route"] == route and r["status"] == STATUS_PENDING
            for r in regions
        )

    review_pending = any(
        r["route"] == ROUTE_REVIEW and r["status"] == STATUS_REVIEW
        for r in regions
    )
    level3 = pending(ROUTE_LEVEL_3)
    level4 = pending(ROUTE_LEVEL_4)
    level5 = pending(ROUTE_LEVEL_5)

    return {
        "level3_pending": level3,
        "level4_pending": level4,
        "level5_pending": level5,
        "review_pending": review_pending,
        "has_residual": level3 or level4 or level5 or review_pending,
    }


def resolve_region(
    state: dict[str, Any],
    candidate_id: str,
    *,
    resolved_by: str,
) -> dict[str, Any]:
    """Retorna nova cópia do estado com uma região de nível resolvida."""
    validate_page_state(state)
    updated = deepcopy(state)

    for region in updated["regions"]:
        if region["candidate_id"] != candidate_id:
            continue
        if region["route"] not in LEVEL_ROUTES:
            raise ValueError("Only LEVEL_3/4/5 regions can be resolved.")
        if region["status"] != STATUS_PENDING:
            raise ValueError("Region is not pending.")
        if not resolved_by:
            raise ValueError("resolved_by is required.")
        region["status"] = STATUS_RESOLVED
        region["resolved_by"] = resolved_by
        validate_page_state(updated)
        return updated

    raise KeyError(f"Unknown candidate_id: {candidate_id}")
