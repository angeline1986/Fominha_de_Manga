from dataclasses import dataclass
from pathlib import Path

from config.data_paths import OUTPUT_ROOT
from central_v2.backend.routes.catalog import catalog_response
from central_v2.backend.routes.health import health_response


@dataclass(frozen=True)
class RouteResponse:
    status: int
    body: bytes
    content_type: str = "application/json; charset=utf-8"


def dispatch_get(
    path: str,
    output_root: Path = OUTPUT_ROOT,
) -> RouteResponse | None:
    if path == "/health":
        return RouteResponse(
            status=200,
            body=health_response(),
        )

    if path == "/api/catalog":
        return RouteResponse(
            status=200,
            body=catalog_response(output_root),
        )

    return None
