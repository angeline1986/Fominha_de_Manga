import json

from config.data_paths import OUTPUT_ROOT
from central_v2.backend.routes.response import RouteResponse
from central_v2.backend.state.manga_state import resolve_manga
from processamento.merge_manual.api import get_saved_merge_manual_proposals


def response(query, output_root=OUTPUT_ROOT):
    provider = (query.get("provider") or [""])[0]
    name = (query.get("manga") or [""])[0]
    if not provider or not name:
        return RouteResponse(400, b'{"error":"provider e manga sao obrigatorios"}')
    try:
        manga = resolve_manga(output_root, provider, name)
        payload = get_saved_merge_manual_proposals(manga)
        return RouteResponse(200, json.dumps(payload, ensure_ascii=False).encode())
    except (OSError, ValueError) as exc:
        body = json.dumps({"error": str(exc)}, ensure_ascii=False).encode()
        return RouteResponse(400, body)
