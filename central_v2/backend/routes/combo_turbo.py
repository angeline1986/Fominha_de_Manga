"""HTTP routes for Combo Turbo planning and isolated batch jobs."""
import json
import re
from urllib.parse import urlparse

from central_v2.backend.orchestration.combo_turbo.api_contract import (
    PlanConflictError, plan_request, request_context,
)
from central_v2.backend.orchestration.combo_turbo.job_api import start_job
from central_v2.backend.orchestration.combo_turbo.job_store import persisted_result, public_job
from central_v2.backend.routes.response import RouteResponse

PLAN_ROUTE = "/api/combo-turbo/plan"
JOBS_ROUTE = "/api/combo-turbo/jobs"
_JOB = re.compile(r"/api/combo-turbo/jobs/([a-f0-9]{32})\Z")
_RESULT = re.compile(r"/api/combo-turbo/jobs/([a-f0-9]{32})/result\Z")


def dispatch_post(path, payload, output_root):
    route = urlparse(path).path
    try:
        if route == PLAN_ROUTE:
            context = request_context(payload, output_root,
                                      fields={"provider", "manga", "chapters"})
            return RouteResponse(200, _json(plan_request(context)))
        if route == JOBS_ROUTE:
            job = start_job(payload, output_root)
            return RouteResponse(202, _json({"job": job,
                "status_url": f"{JOBS_ROUTE}/{job['id']}",
                "result_url": f"{JOBS_ROUTE}/{job['id']}/result"}))
    except PlanConflictError as exc:
        return RouteResponse(409, _json({"error": str(exc), "reason": "PLAN_CONTEXT_CHANGED"}))
    except ValueError as exc:
        return RouteResponse(400, _json({"error": str(exc)}))
    except (OSError, RuntimeError) as exc:
        return RouteResponse(500, _json({"error": str(exc)}))
    return None


def dispatch_get(path, output_root):
    route = urlparse(path).path
    match = _RESULT.fullmatch(route)
    if match:
        status, payload = persisted_result(match.group(1), output_root)
        return RouteResponse(status, _json(payload))
    match = _JOB.fullmatch(route)
    if match:
        job = public_job(match.group(1))
        return (RouteResponse(404, _json({"error": "Job Combo Turbo não encontrado."}))
                if job is None else RouteResponse(200, _json({"job": job})))
    return None


def _json(payload):
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
