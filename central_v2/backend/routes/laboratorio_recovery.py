"""Read-only recovery of the latest verified Artístico preview for a source image."""
import json
from pathlib import Path
import re
from urllib.parse import urlencode

from central_v2.backend.orchestration.textoff_special.artifacts import (
    contained_file, read_json, sha256,
)
from central_v2.backend.orchestration.textoff_merged.laboratorio_final_candidate import image_size
from central_v2.backend.routes.laboratorio_source import resolve_source
from central_v2.backend.routes.response import RouteResponse
from central_v2.backend.orchestration.textoff_special.catalog import ROOT
from central_v2.backend.orchestration.textoff_special.run_paths import roots

STAGING = ROOT / "reports/experimentos/textoff_laboratorio"
FIELDS = ("provider", "manga", "chapter", "page", "source")
RUN_ID = re.compile(r"[0-9a-f]{32}\Z")


def _json(body, status=200):
    return RouteResponse(status, json.dumps(body, ensure_ascii=False).encode("utf-8"))


def recent_response(query, output_root):
    try:
        payload = {key: (query.get(key) or [""])[0] for key in FIELDS}
        if payload["source"] == "file":
            payload["path"] = (query.get("path") or [""])[0]
        manga, path, chapter, filename = resolve_source(payload, output_root)
        source_hash = sha256(path)
        requests = (item for root in roots(manga, "textoff_laboratorio", legacy=STAGING)
                    for item in root.glob("*/request.json"))
        for request_file in sorted(requests, key=lambda item: item.stat().st_mtime, reverse=True):
            folder = request_file.parent
            if not RUN_ID.fullmatch(folder.name):
                continue
            try:
                request = read_json(request_file)
                source = request.get("source")
                if (request.get("run_id") != folder.name
                        or request.get("treatment") != "estilizado"
                        or not isinstance(source, dict)
                        or source.get("path") != str(path)
                        or source.get("sha256") != source_hash
                        or source.get("manga") != str(manga)
                        or source.get("chapter") != chapter
                        or source.get("filename") != filename):
                    continue
                manifest = read_json(folder / "manifest.json")
                if (manifest.get("run_id") != folder.name
                        or manifest.get("source") != source
                        or manifest.get("execution_status") != "succeeded"):
                    continue
                result = contained_file(folder, manifest["result_file"])
                snapshot = contained_file(folder, "input/source.png")
                if (sha256(snapshot) != source_hash
                        or sha256(result) != manifest["validation"]["result_sha256"]):
                    continue
                image_size(result)
                return _json({"result": {"treatment": "estilizado", "run_id": folder.name,
                    "image_url": "/api/textoff/laboratorio/estilizado/image?"
                    + urlencode({"run_id": folder.name, "provider": manga.parent.name,
                                 "manga": manga.name})}})
            except (OSError, ValueError, KeyError, TypeError):
                continue
        return _json({"result": None})
    except (OSError, ValueError, KeyError, TypeError) as error:
        return _json({"error": str(error)}, 400)
