from central_v2.backend.routes.response import RouteResponse


def shutdown_response(path: str) -> RouteResponse | None:
    if path != "/api/shutdown":
        return None
    return RouteResponse(status=200, body=b'{"status":"shutting_down"}')
