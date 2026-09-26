import json
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from config.data_paths import OUTPUT_ROOT
from central_v2.backend.routes.catalog import catalog_response
from central_v2.backend.routes.health import health_response
from central_v2.backend.routes.state import state_response
from central_v2.backend.routes.static import static_response


@dataclass(frozen=True)
class RouteResponse:
    status: int
    body: bytes
    content_type: str = "application/json; charset=utf-8"


def dispatch_get(
    path: str,
    output_root: Path = OUTPUT_ROOT,
) -> RouteResponse | None:
    request = urlparse(path)

    if request.path == "/health":
        return RouteResponse(
            status=200,
            body=health_response(),
        )

    if request.path == "/api/catalog":
        return RouteResponse(
            status=200,
            body=catalog_response(output_root),
        )

    if request.path == "/api/state":
        query = parse_qs(request.query)
        provider = (query.get("provider") or [""])[0]
        manga_name = (query.get("manga") or [""])[0]

        if not provider or not manga_name:
            return RouteResponse(
                status=400,
                body=json.dumps(
                    {"error": "provider e manga são obrigatórios"},
                    ensure_ascii=False,
                    separators=(",", ":"),
                ).encode("utf-8"),
            )

        try:
            body = state_response(
                provider,
                manga_name,
                output_root,
            )
        except ValueError as exc:
            return RouteResponse(
                status=400,
                body=json.dumps(
                    {"error": str(exc)},
                    ensure_ascii=False,
                    separators=(",", ":"),
                ).encode("utf-8"),
            )

        return RouteResponse(
            status=200,
            body=body,
        )

    static = static_response(request.path)

    if static is not None:
        return RouteResponse(
            status=200,
            body=static.body,
            content_type=static.content_type,
        )

    return None
