"""HTTP contract for verified final-page history and restoration."""
import json
from pathlib import Path

from PIL import UnidentifiedImageError

from central_v2.backend.orchestration.textoff_merged.laboratorio_final_history import (
    FIELDS, history_image, inspect,
)
from central_v2.backend.orchestration.textoff_merged.laboratorio_final_restore import restore
from central_v2.backend.routes.response import RouteResponse

ERRORS = (ValueError, OSError, KeyError, TypeError, UnidentifiedImageError)


def history_response(query: dict, output_root: Path) -> RouteResponse:
    try:
        identity = {key: (query.get(key) or [""])[0] for key in FIELDS}
        body = inspect(identity, output_root)
        return RouteResponse(200, json.dumps(body, ensure_ascii=False).encode("utf-8"))
    except ERRORS as error:
        return RouteResponse(400, json.dumps({"error": str(error)}, ensure_ascii=False).encode("utf-8"))


def image_response(query: dict, output_root: Path) -> RouteResponse:
    try:
        return RouteResponse(200, history_image(query, output_root), "image/png")
    except ERRORS:
        return RouteResponse(404, json.dumps({"error": "Prévia histórica indisponível ou obsoleta."},
                                              ensure_ascii=False).encode("utf-8"))


def restore_response(payload: object, output_root: Path) -> RouteResponse:
    try:
        body = restore(payload, output_root)
        return RouteResponse(200, json.dumps(body, ensure_ascii=False).encode("utf-8"))
    except ERRORS as error:
        status = 409 if "PROPOSTA_OBSOLETA" in str(error) else 400
        return RouteResponse(status, json.dumps({"error": str(error)},
                                                ensure_ascii=False).encode("utf-8"))
