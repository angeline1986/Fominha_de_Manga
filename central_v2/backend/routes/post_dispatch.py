"""Dispatch POST requests to Central V2 route handlers."""

from pathlib import Path
from urllib.parse import urlparse
from config.data_paths import OUTPUT_ROOT
from central_v2.backend.routes.auto_merge.level1 import execute_response
from central_v2.backend.routes.auto_merge.level2 import execute_level2_response
from central_v2.backend.routes.auto_merge.level3 import execute_level3_response
from central_v2.backend.routes.auto_merge.level4 import execute_level4_response
from central_v2.backend.routes.auto_merge.level5 import execute_level5_response
from central_v2.backend.routes.auto_merge.folder import open_auto_merge_folder_response
from central_v2.backend.routes.export_files import export_response
from central_v2.backend.routes.pdf_execute import execute_pdf_response
from central_v2.backend.routes.bubble_sommelier import execute_response as execute_bubble_sommelier_response
from central_v2.backend.routes.shutdown import shutdown_response
from central_v2.backend.routes.merge_manual import merge_manual_apply_response, merge_manual_proposal_response
from central_v2.backend.routes.textoff_merged_router import dispatch_textoff_merged_post
from central_v2.backend.routes.balanceamento import balanceamento_job_response
from central_v2.backend.routes.response import RouteResponse
from central_v2.backend.routes.laboratorio_dispatch import dispatch_laboratorio_post


def dispatch_post(path: str, payload: object, output_root: Path = OUTPUT_ROOT) -> RouteResponse | None:
    handled, response = dispatch_laboratorio_post(path, payload, output_root)
    if handled:
        return response
    if urlparse(path).path in {"/api/export/simulate", "/api/export/execute"}:
        return export_response(urlparse(path).path.rsplit("/", 1)[-1], payload, output_root)
    if urlparse(path).path == "/api/pdf/execute":
        return execute_pdf_response(payload, output_root)
    if path == "/api/shutdown":
        return shutdown_response(path)
    if urlparse(path).path == "/api/auto-merge/level1/execute":
        return execute_response(payload, output_root)
    if urlparse(path).path == "/api/auto-merge/level2/execute":
        return execute_level2_response(payload, output_root)
    if urlparse(path).path == "/api/auto-merge/level3/execute":
        return execute_level3_response(payload, output_root)
    if urlparse(path).path == "/api/auto-merge/level4/execute":
        return execute_level4_response(payload, output_root)
    if urlparse(path).path == "/api/auto-merge/level5/execute":
        return execute_level5_response(payload, output_root)
    if urlparse(path).path == "/api/merge-manual/proposal":
        return merge_manual_proposal_response(payload, output_root)
    if urlparse(path).path == "/api/textoff/sommelier/execute":
        return execute_bubble_sommelier_response(payload, output_root)

    textoff_response = dispatch_textoff_merged_post(path, payload, output_root)
    if textoff_response is not None:
        return textoff_response
    if urlparse(path).path == "/api/merge-manual/apply":
        return merge_manual_apply_response(payload, output_root)
    if urlparse(path).path in {
        "/api/balanceamento/validate", "/api/balanceamento/prepare",
        "/api/balanceamento/proposal", "/api/balanceamento/apply",
    }:
        action = urlparse(path).path.rsplit("/", 1)[-1]
        return balanceamento_job_response(action, payload, output_root)
    if urlparse(path).path == "/api/auto-merge/open-folder":
        return open_auto_merge_folder_response(payload, output_root)
    return None
