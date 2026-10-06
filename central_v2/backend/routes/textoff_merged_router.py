"""Route dispatch for the independent TextOff Merged flow."""
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from config.data_paths import OUTPUT_ROOT
from central_v2.backend.routes.textoff_comparison import comparison_response
from central_v2.backend.routes.textoff_residue_occurrences import (
    ROUTE as RESIDUE_OCCURRENCES_ROUTE, residue_occurrences_get_response,
    residue_occurrences_post_response,
)
from central_v2.backend.routes.response import RouteResponse
from central_v2.backend.routes.special_treatments import (
    EXECUTE_ROUTE as SPECIAL_TREATMENTS_EXECUTE_ROUTE,
    execute_special_treatments_response,
)
from central_v2.backend.routes.textoff_merged import (
    execute_textoff_merged_level1_response, execute_textoff_merged_level2_response,
    execute_textoff_merged_level3_response, execute_textoff_merged_response,
    execute_textoff_merged_special_response, textoff_merged_level3_image_response,
    textoff_merged_level_response, textoff_merged_response,
)


def dispatch_textoff_merged_get(request, output_root: Path) -> RouteResponse | None:
    if request.path == RESIDUE_OCCURRENCES_ROUTE:
        return residue_occurrences_get_response(parse_qs(request.query), output_root)
    if request.path in {"/api/textoff/comparison", "/api/textoff/comparison/image"}:
        return comparison_response(parse_qs(request.query), output_root,
                                   image=request.path.endswith("/image"))
    if request.path == "/api/textoff/merged":
        return textoff_merged_response(parse_qs(request.query), output_root)
    levels = {"level1": "I", "level2": "II", "level3": "III",
              "levelIV": "IV", "levelV": "V"}
    name = request.path.rsplit("/", 1)[-1]
    if name in levels and request.path.startswith("/api/textoff/merged/"):
        return textoff_merged_level_response(levels[name], parse_qs(request.query), output_root)
    if request.path == "/api/textoff/merged/level3/image":
        return textoff_merged_level3_image_response(parse_qs(request.query), output_root)
    return None


def dispatch_textoff_merged_post(path: str, payload: object,
                                 output_root: Path = OUTPUT_ROOT) -> RouteResponse | None:
    route = urlparse(path).path
    if route == RESIDUE_OCCURRENCES_ROUTE:
        return residue_occurrences_post_response(payload, output_root)
    if route == SPECIAL_TREATMENTS_EXECUTE_ROUTE:
        return execute_special_treatments_response(payload, output_root)
    handlers = {
        "/api/textoff/merged/execute": execute_textoff_merged_response,
        "/api/textoff/merged/level1/execute": execute_textoff_merged_level1_response,
        "/api/textoff/merged/level2/execute": execute_textoff_merged_level2_response,
        "/api/textoff/merged/level3/execute": execute_textoff_merged_level3_response,
    }
    handler = handlers.get(route)
    if handler is not None:
        return handler(payload, output_root)
    for level in ("IV", "V"):
        if route == f"/api/textoff/merged/level{level}/execute":
            return execute_textoff_merged_special_response(level, payload, output_root)
    return None
