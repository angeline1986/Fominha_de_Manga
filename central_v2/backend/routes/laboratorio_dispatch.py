"""Route dispatch for the experimental Laboratory endpoints."""

from pathlib import Path
from urllib.parse import parse_qs, urlparse

from central_v2.backend.routes.laboratorio_degrade import (
    authorization_candidates as lab_degrade_candidates,
    confirm_authorization as lab_degrade_authorize,
    execute as lab_degrade_execute,
    result_image as lab_degrade_image,
)
from central_v2.backend.routes.laboratorio_pages import response as laboratorio_pages_response
from central_v2.backend.routes.laboratorio_tratamentos import (
    execute_smooth as lab_smooth_execute,
    execute_stylized as lab_stylized_execute,
    start_stylized_job as lab_stylized_start_job,
    result_image as lab_stylized_image,
)
from central_v2.backend.routes.response import RouteResponse
from config.data_paths import OUTPUT_ROOT


def dispatch_laboratorio_get(request, output_root: Path = OUTPUT_ROOT) -> tuple[bool, RouteResponse | None]:
    if request.path in {"/api/textoff/laboratorio/pages", "/api/textoff/laboratorio/pages/image"}:
        response = laboratorio_pages_response(
            parse_qs(request.query), output_root,
            image=request.path.endswith("/image"),
        )
        return True, response

    if request.path == "/api/textoff/laboratorio/degrade/image":
        return True, lab_degrade_image(parse_qs(request.query))
    if request.path == "/api/textoff/laboratorio/estilizado/image":
        return True, lab_stylized_image(parse_qs(request.query))
    if request.path == "/api/textoff/laboratorio/gradiente_suave/image":
        return True, lab_stylized_image(parse_qs(request.query), "gradiente_suave")
    return False, None


def dispatch_laboratorio_post(
    path: str, payload: object, output_root: Path = OUTPUT_ROOT,
) -> tuple[bool, RouteResponse | None]:
    route = urlparse(path).path
    if route == "/api/textoff/laboratorio/degrade/execute":
        return True, lab_degrade_execute(payload, output_root)
    if route == "/api/textoff/laboratorio/degrade/authorization-candidates":
        return True, lab_degrade_candidates(payload)
    if route == "/api/textoff/laboratorio/degrade/authorize":
        return True, lab_degrade_authorize(payload, output_root)
    if route == "/api/textoff/laboratorio/estilizado/job":
        return True, lab_stylized_start_job(payload, output_root)
    if route == "/api/textoff/laboratorio/estilizado/execute":
        return True, lab_stylized_execute(payload, output_root)
    if route == "/api/textoff/laboratorio/gradiente_suave/execute":
        return True, lab_smooth_execute(payload, output_root)
    return False, None
