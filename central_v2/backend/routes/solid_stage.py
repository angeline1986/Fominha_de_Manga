"""Stage 05 API; preview only, no automatic downstream promotion."""
import json
from pathlib import Path
from urllib.parse import urlencode
from PIL import Image
from central_v2.backend.jobs.manager import submit
from central_v2.backend.routes.response import RouteResponse
from central_v2.backend.routes.textoff_merged import _context, _value
from central_v2.backend.state.manga_state import resolve_manga
from central_v2.backend.orchestration.textoff_merged.auto_cleaner_check_manifest import _validate_chapter
from central_v2.backend.orchestration.textoff_merged.solid_stage import (
    STAGE, execute_chapter, rows_for, source_for,
)
from central_v2.backend.orchestration.textoff_merged.stages import stage_chapter
from central_v2.backend.routes.laboratorio_solidos import _sha

ROUTE = "/api/textoff/solidos"


def reply(data, code=200):
    return RouteResponse(code, json.dumps(data, ensure_ascii=False).encode("utf-8"))


def context(payload, output_root):
    provider, name = _context(payload, output_root)
    return resolve_manga(output_root, provider, name), {"provider": provider, "obra": name}


def overview(query, output_root):
    try:
        manga, document = context(query, output_root)
        check_root = manga / "FLUXO_SECUNDARIO/04_TEXTO_OFF/04_AUTO_CLEANER_CHECK"
        rows = []
        if check_root.is_dir():
            for folder in sorted(check_root.iterdir(), key=lambda p: p.name):
                if not folder.is_dir() or folder.is_symlink():
                    continue
                chapter = folder.name
                _validate_chapter(chapter)
                selections, _ = rows_for(manga, {**document, "capitulo": chapter}, chapter)
                if not selections:
                    continue
                result = stage_chapter(manga, STAGE, chapter, read_legacy=False)
                pages = sorted({row.get("page") for row in selections if isinstance(row.get("page"), str)})
                rows.append({"chapter": chapter, "regions": len(selections), "pages": pages,
                             "processed": (result / "solid-white-manifest.json").is_file()})
        return reply({"chapters": rows, **{"provider":document["provider"],"manga":document["obra"]}})
    except (ValueError, OSError, TypeError) as exc:
        return reply({"error": str(exc)}, 400)


def execute(payload, output_root):
    try:
        if not isinstance(payload, dict):
            raise ValueError("Requisição inválida")
        manga, document = context(payload, output_root)
        chapter = payload.get("chapter")
        _validate_chapter(chapter)
        rows, _ = rows_for(manga, {**document, "capitulo": chapter}, chapter)
        if not rows:
            raise ValueError("Nenhuma área Sólidos aprovada")
        if stage_chapter(manga, STAGE, chapter, read_legacy=False).exists():
            raise ValueError("Prévia já existente; resultados preservados")
        def run(update, _job_id):
            result = execute_chapter(manga, {**document, "capitulo": chapter}, chapter)
            update(chapter, {"completed": 1, "total": 1, "percent": 100,
                             "message": "Prévia Sólidos salva"})
            return [result]
        return reply({"job": submit(run, total=1)}, 202)
    except (ValueError, OSError) as exc:
        return reply({"error": str(exc)}, 400)


def page_image(query, output_root):
    try:
        manga, document = context(query, output_root)
        chapter, page, kind = (_value(query, k) for k in ("chapter", "page", "kind"))
        _validate_chapter(chapter)
        folder = stage_chapter(manga, STAGE, chapter, read_legacy=False)
        record = json.loads((folder / "solid-white-manifest.json").read_text(encoding="utf-8"))
        if (record.get("provider") != document["provider"] or record.get("manga") != document["obra"]
                or record.get("chapter") != chapter or record.get("preview_only") is not True):
            raise ValueError("Prévia incompatível")
        item = next((r for r in record["pages"] if r.get("page") == page), None)
        if item is None:
            raise ValueError("Página não faz parte desta prévia")
        if kind == "before":
            target = source_for(manga, chapter, page)
            expected = item["source_sha256"]
        elif kind in ("after", "mask"):
            suffix = "clean" if kind == "after" else "mask"
            target = folder / suffix / (Path(page).stem + f"_{suffix}.png")
            expected = item["result_sha256" if kind == "after" else "mask_sha256"]
        else:
            raise ValueError("Tipo inválido")
        if _sha(target) != expected:
            raise ValueError("Imagem modificada após o processamento")
        return RouteResponse(200, target.read_bytes(), "image/png")
    except (ValueError, OSError, KeyError, TypeError) as exc:
        return reply({"error": str(exc)}, 404)
