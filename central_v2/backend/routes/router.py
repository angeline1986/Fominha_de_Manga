import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from config.data_paths import OUTPUT_ROOT
from central_v2.backend.routes.auto_merge.level1 import execute_response, level1_response
from central_v2.backend.routes.auto_merge.level2 import execute_level2_response, level2_response
from central_v2.backend.routes.auto_merge.level3 import execute_level3_response, level3_response
from central_v2.backend.routes.auto_merge.level4 import execute_level4_response, level4_response
from central_v2.backend.routes.auto_merge.level5 import execute_level5_response, level5_response
from central_v2.backend.routes.auto_merge.folder import open_auto_merge_folder_response
from central_v2.backend.routes.catalog import catalog_response
from central_v2.backend.routes.health import health_response
from central_v2.backend.routes.jobs import job_response
from central_v2.backend.routes.bubble_sommelier import (
    crop_response as bubble_sommelier_crop_response,
    execute_response as execute_bubble_sommelier_response,
    response as bubble_sommelier_response,
    review_response as bubble_sommelier_review_response,
)
from central_v2.backend.routes.shutdown import shutdown_response
from central_v2.backend.routes.state import state_response
from central_v2.backend.routes.merge_manual import (
    merge_manual_apply_response, merge_manual_image_response,
    merge_manual_proposal_image_response, merge_manual_proposal_response,
    merge_manual_response,
)
from central_v2.backend.routes.static import static_response
from central_v2.backend.routes.textoff_merged_router import (
    dispatch_textoff_merged_get, dispatch_textoff_merged_post,
)
from central_v2.backend.routes.balanceamento import balanceamento_job_response, balanceamento_response
from central_v2.backend.routes.balanceamento_media import balanceamento_image_response
from central_v2.backend.routes.response import RouteResponse
from central_v2.backend.routes.textoff_special import (
    execute_special_response, special_image_response, special_level_response,
    special_result_response,
)
from central_v2.backend.routes.special_treatments import (
    ROUTE as SPECIAL_TREATMENTS_ROUTE, IMAGE_ROUTE as SPECIAL_TREATMENTS_IMAGE_ROUTE,
    special_treatments_response, styled_preview_image_response,
)

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

    if request.path == "/api/merge-manual":
        return merge_manual_response(parse_qs(request.query), output_root)

    if request.path == "/api/balanceamento":
        return balanceamento_response(parse_qs(request.query), output_root)

    if request.path == "/api/balanceamento/image":
        return balanceamento_image_response(parse_qs(request.query), output_root)

    if request.path == "/api/merge-manual/image":
        return merge_manual_image_response(parse_qs(request.query), output_root)

    if request.path == "/api/textoff/sommelier":
        return bubble_sommelier_response(parse_qs(request.query), output_root)

    if request.path == "/api/textoff/sommelier/review":
        return bubble_sommelier_review_response(parse_qs(request.query), output_root)

    if request.path == "/api/textoff/sommelier/crop":
        return bubble_sommelier_crop_response(parse_qs(request.query), output_root)

    textoff_response = dispatch_textoff_merged_get(request, output_root)
    if textoff_response is not None:
        return textoff_response

    if request.path == SPECIAL_TREATMENTS_ROUTE:
        return special_treatments_response(parse_qs(request.query), output_root)
    if request.path == SPECIAL_TREATMENTS_IMAGE_ROUTE:
        return styled_preview_image_response(parse_qs(request.query), output_root)
    for level in ("VI", "VII", "VIII"):
        if request.path == f"/api/textoff/special/level{level}":
            return special_level_response(level, parse_qs(request.query), output_root)
    if request.path == "/api/textoff/special/image":
        return special_image_response(parse_qs(request.query), output_root)
    if request.path == "/api/textoff/special/result":
        return special_result_response(parse_qs(request.query))

    if request.path == "/api/merge-manual/proposal/image":
        return merge_manual_proposal_image_response(parse_qs(request.query), output_root)

    if request.path == "/api/auto-merge/level1":
        return level1_response(parse_qs(request.query), output_root)

    if request.path == "/api/auto-merge/level2":
        return level2_response(parse_qs(request.query), output_root)

    if request.path == "/api/auto-merge/level3":
        return level3_response(parse_qs(request.query), output_root)

    if request.path == "/api/auto-merge/level4":
        return level4_response(parse_qs(request.query), output_root)

    if request.path == "/api/auto-merge/level5":
        return level5_response(parse_qs(request.query), output_root)

    job = job_response(request.path)
    if job is not None:
        return job

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


def dispatch_post(path: str, payload: object, output_root: Path = OUTPUT_ROOT) -> RouteResponse | None:
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
