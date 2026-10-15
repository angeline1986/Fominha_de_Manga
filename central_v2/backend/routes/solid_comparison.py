"""Read-only comparison of immutable Stage 05 previews, through shared viewer."""
import hashlib
import json
from urllib.parse import parse_qs

from central_v2.backend.routes.response import RouteResponse
from central_v2.backend.routes.textoff_merged import _value
from central_v2.backend.routes.solid_stage import context, page_image
from central_v2.backend.orchestration.textoff_merged.solid_stage import STAGE
from central_v2.backend.orchestration.textoff_merged.stages import stage_chapter
from central_v2.backend.orchestration.textoff_merged.auto_cleaner_check_manifest import _validate_chapter


def _reply(body, status=200):
    return RouteResponse(status, json.dumps(body, ensure_ascii=False).encode("utf-8"))


def response(query, output_root, *, image=False):
    try:
        manga, document = context(query, output_root)
        chapter = _value(query, "chapter")
        _validate_chapter(chapter)
        path = stage_chapter(manga, STAGE, chapter, read_legacy=False) / "solid-white-manifest.json"
        record = json.loads(path.read_text(encoding="utf-8"))
        if (record.get("provider") != document["provider"] or record.get("manga") != document["obra"]
                or record.get("chapter") != chapter or record.get("preview_only") is not True):
            raise ValueError("Manifest incompatível")
        pages = record["pages"]
        if not isinstance(pages, list):
            raise ValueError("Manifest inválido")
        entries = []
        for index, item in enumerate(pages):
            name = item["page"]
            signature = "|".join(str(item[k]) for k in ("page", "source_sha256", "result_sha256"))
            version = hashlib.sha256(signature.encode("utf-8")).hexdigest()
            entries.append({"id": str(index), "name": name, "version": version,
                            "residue_occurrence_count": 0})
        if not image:
            return _reply({"pages": entries, "experimental": True})
        idx = _value(query, "page")
        side = _value(query, "side")
        if not isinstance(idx, str) or not idx.isdecimal() or side not in ("before", "after"):
            raise ValueError("Parâmetros inválidos")
        number = int(idx)
        if number >= len(entries) or _value(query, "version") != entries[number]["version"]:
            raise ValueError("Versão não corresponde à prévia")
        image_query = {key: [value] for key, value in {
            "provider": document["provider"], "manga": document["obra"],
            "chapter": chapter, "page": entries[number]["name"], "kind": side,
        }.items()}
        return page_image(image_query, output_root)
    except (OSError, ValueError, TypeError, KeyError, IndexError, json.JSONDecodeError):
        return _reply({"error": "Comparação Sólidos indisponível ou desatualizada."}, 404)
