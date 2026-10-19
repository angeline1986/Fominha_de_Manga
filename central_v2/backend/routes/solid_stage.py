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
    STAGE, decision_sha256, execute_chapter, rows_for, source_for,
)
from central_v2.backend.orchestration.textoff_merged.solid_reexecution import reexecute_page
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
                selections, check_hash = rows_for(manga, {**document, "capitulo": chapter}, chapter)
                result = stage_chapter(manga, STAGE, chapter, read_legacy=False)
                manifest_path = result / "solid-white-manifest.json"
                saved = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {}
                saved_pages = {row.get("page"): row for row in saved.get("pages", [])
                               if isinstance(row, dict) and isinstance(row.get("page"), str)}
                if not selections and not saved_pages:
                    continue
                grouped = {}
                for item in selections:
                    grouped.setdefault(item.get("page"), []).append(item)
                page_rows = []
                for page in sorted(set(grouped) | set(saved_pages)):
                    selected = grouped.get(page, [])
                    previous = saved_pages.get(page)
                    processed = isinstance(previous, dict)
                    outdated = None
                    if processed and isinstance(previous.get("decision_sha256"), str):
                        outdated = previous["decision_sha256"] != decision_sha256(selected)
                        try:
                            outdated = outdated or previous.get("source_sha256") != _sha(
                                source_for(manga, chapter, page))
                        except (ValueError, OSError):
                            outdated = True
                    elif processed:
                        outdated = previous.get("check_sha256", saved.get("check_sha256")) != check_hash
                    page_rows.append({"name": page, "regions": len(selected),
                        "processed": processed, "outdated": outdated,
                        "run_id": previous.get("run_id") if processed else None,
                        "result_sha256": previous.get("result_sha256") if processed else None,
                        "check_sha256": check_hash})
                rows.append({"chapter": chapter, "regions": len(selections), "pages": page_rows,
                             "processed": bool(saved_pages)})
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
        page = payload.get("page")
        rows, _ = rows_for(manga, {**document, "capitulo": chapter}, chapter)
        if not rows and page is None:
            raise ValueError("Nenhuma área Sólidos aprovada")
        if page is not None:
            target = stage_chapter(manga, STAGE, chapter, read_legacy=False)
            prior_path = target / "solid-white-manifest.json"
            prior_pages = []
            if prior_path.is_file():
                prior = json.loads(prior_path.read_text(encoding="utf-8"))
                prior_pages = [row.get("page") for row in prior.get("pages", [])
                               if isinstance(row, dict)]
            if (not isinstance(page, str) or Path(page).name != page
                    or (not any(row.get("page") == page for row in rows)
                        and page not in prior_pages)):
                raise ValueError("Selecione uma página com áreas Sólidos aprovadas.")
            expected = payload.get("expected_result_sha256")
            if not isinstance(expected, str) or len(expected) != 64:
                raise ValueError("Versão da prévia anterior ausente para reexecução.")
            if not target.is_dir():
                raise ValueError("A página ainda não possui uma prévia Sólidos para reexecutar.")
        elif stage_chapter(manga, STAGE, chapter, read_legacy=False).exists():
            raise ValueError("Prévia já existente; resultados preservados")
        def run(update, _job_id):
            result = (reexecute_page(manga, document, chapter, page, expected)
                      if page is not None else
                      execute_chapter(manga, {**document, "capitulo": chapter}, chapter))
            update(chapter, {"completed": 1, "total": 1, "percent": 100,
                             "message": (f"Prévia Sólidos atualizada: {page}" if page
                                         else "Prévia Sólidos salva")})
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
            expected = item["source_sha256"]
            target = source_for(manga, chapter, page, expected_sha256=expected)
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
