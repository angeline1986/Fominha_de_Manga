"""Read-only HTTP contract for reviewing a Laboratory final candidate."""
import json
from pathlib import Path

from PIL import UnidentifiedImageError

from central_v2.backend.orchestration.textoff_merged.laboratorio_final_review import (
    inspect, review_image,
)
from central_v2.backend.orchestration.textoff_merged.laboratorio_final_apply import apply
from central_v2.backend.routes.response import RouteResponse


def proposal_response(payload: object, output_root: Path) -> RouteResponse:
    try:
        proposal = inspect(payload, output_root)
        return RouteResponse(200, json.dumps(proposal, ensure_ascii=False).encode("utf-8"))
    except (ValueError, OSError, KeyError, TypeError, UnidentifiedImageError) as error:
        return RouteResponse(400, json.dumps({"error": str(error)}, ensure_ascii=False).encode("utf-8"))


def image_response(query: dict, output_root: Path) -> RouteResponse:
    try:
        return RouteResponse(200, review_image(query, output_root), "image/png")
    except (ValueError, OSError, KeyError, TypeError, UnidentifiedImageError):
        return RouteResponse(404, json.dumps({"error": "Prévia indisponível ou obsoleta."},
                                              ensure_ascii=False).encode("utf-8"))


def apply_response(payload: object, output_root: Path) -> RouteResponse:
    try:
        result = apply(payload, output_root)
        return RouteResponse(200, json.dumps(result, ensure_ascii=False).encode("utf-8"))
    except (ValueError, OSError, KeyError, TypeError, UnidentifiedImageError) as error:
        status = 409 if "PROPOSTA_OBSOLETA" in str(error) else 400
        return RouteResponse(status, json.dumps({"error": str(error)},
                                                ensure_ascii=False).encode("utf-8"))
