import mimetypes
from dataclasses import dataclass
from pathlib import Path


FRONTEND_ROOT = (
    Path(__file__).resolve().parents[2] / "frontend"
).resolve()


@dataclass(frozen=True)
class StaticResponse:
    body: bytes
    content_type: str


def static_response(
    request_path: str,
    frontend_root: Path = FRONTEND_ROOT,
) -> StaticResponse | None:
    base = frontend_root.resolve()
    relative_path = "index.html" if request_path in {"", "/"} else request_path.lstrip("/")
    target = (base / relative_path).resolve()

    if not target.is_relative_to(base):
        return None

    if not target.is_file():
        return None

    content_type = (
        mimetypes.guess_type(target.name)[0]
        or "application/octet-stream"
    )

    return StaticResponse(
        body=target.read_bytes(),
        content_type=content_type,
    )
