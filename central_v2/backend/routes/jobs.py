"""Read-only job status endpoint."""
import json
import re

from central_v2.backend.jobs.manager import get_job
from central_v2.backend.routes.response import RouteResponse


def job_response(path: str) -> RouteResponse | None:
    match = re.fullmatch(r"/api/jobs/([a-f0-9]{32})", path)
    if match is None:
        return None
    job = get_job(match.group(1))
    if job is None:
        return RouteResponse(404, _json({"error": "Execução não encontrada."}))
    return RouteResponse(200, _json({"job": job}))


def _json(payload: dict) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
