from dataclasses import dataclass


@dataclass(frozen=True)
class RouteResponse:
    status: int
    body: bytes
    content_type: str = "application/json; charset=utf-8"
