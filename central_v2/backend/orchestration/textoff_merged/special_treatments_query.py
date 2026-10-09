"""Read chapter worklists from the persisted Special Treatments projection."""
from __future__ import annotations

import json
from pathlib import Path
from PIL import Image

from central_v2.backend.state.sorting import natural_sort_key

from .special_treatments_manifest import MANIFEST_NAME, SCHEMA, STATUSES, TREATMENTS
from .stages import stage_root
from .special_degrade_review import review_pairs
from .special_smooth_review import review_pairs as smooth_review_pairs
from .special_styled_review import review_pairs as styled_review_pairs
from .special_styled_occurrence_input import occurrence_input
from .special_styled_source import detection_input
from .special_page_restore_check import restored_block_reason
from .final_consolidated import read_final_page
from .special_styled_transaction import transaction_lock


def _page_preview(manga: Path, chapter: str, page: str, cache: dict) -> dict | None:
    if page not in cache:
        try:
            _record, image, _digest = read_final_page(manga, chapter, page)
            with Image.open(image) as opened:
                width, height = opened.size
            from central_v2.backend.orchestration.textoff_special.artifacts import sha256
            cache[page] = {"width": width, "height": height, "sha256": sha256(image)}
        except (OSError, ValueError, TypeError, KeyError):
            cache[page] = None
    return cache[page]


def _styled_preview(manga, provider, chapter, item, cache):
    if item["status"] in {"pending", "failed"}:
        try:
            source = detection_input(manga, provider, chapter, item["page"],
                                     item["id"], item["box_pixels"])
            return {"width": source["width"], "height": source["height"],
                    "sha256": source["sha256"], "source": "check"}
        except (OSError, ValueError, TypeError, KeyError):
            return None
    current = _page_preview(manga, chapter, item["page"], cache)
    return {**current, "source": "final"} if current else None


def query_special_treatments(manga: Path, provider: str, treatment: str) -> dict:
    manga = Path(manga).resolve()
    with transaction_lock(manga):
        return _query_special_treatments(manga, provider, treatment)


def _query_special_treatments(manga: Path, provider: str, treatment: str) -> dict:
    if treatment not in TREATMENTS:
        raise ValueError("Tratamento especial inválido.")
    manga = Path(manga).resolve()
    root = stage_root(manga, "SPECIAL_TREATMENTS", read_legacy=False)
    if not root.resolve().is_relative_to(manga):
        raise ValueError("Manifesto Especial fora da obra.")
    chapters = []
    if root.is_dir():
        for folder in sorted(root.iterdir(), key=lambda path: natural_sort_key(path.name)):
            if not folder.is_dir() or not folder.resolve().is_relative_to(root.resolve()):
                continue
            source = folder / MANIFEST_NAME
            if not source.is_file() or not source.resolve().is_relative_to(root.resolve()):
                continue
            payload = json.loads(source.read_text(encoding="utf-8"))
            if (not isinstance(payload, dict) or payload.get("schema") != SCHEMA
                    or payload.get("version") != 1 or payload.get("provider") != provider
                    or payload.get("manga") != manga.name
                    or payload.get("chapter") != folder.name):
                raise ValueError("Manifesto Especial incompatível.")
            buckets = payload.get("treatments")
            if not isinstance(buckets, dict) or not isinstance(buckets.get(treatment), list):
                raise ValueError("Manifesto Especial sem tratamento válido.")
            occurrences = buckets[treatment]
            if not occurrences:
                continue
            if any(not isinstance(item, dict) or item.get("status") not in STATUSES
                   or item.get("treatment") != treatment
                   or not isinstance(item.get("page"), str) for item in occurrences):
                raise ValueError("Ocorrência inválida no Manifesto Especial.")
            pages = sorted({item["page"] for item in occurrences}, key=natural_sort_key)
            states = {item["status"] for item in occurrences}
            status = ("failed" if treatment in {"degrade", "gradiente_suave"} and "failed" in states else
                      "pending" if "pending" in states else
                      "failed" if "failed" in states else
                      "processed" if "processed" in states else "no_change")
            review_available = False
            reexecution_blocked, reexecution_block_reason = False, None
            available_occurrences = []
            if treatment == "estilizado":
                previews, restored_blocks = {}, {}
                completed_pages = {item["page"] for item in occurrences
                                   if item["status"] in {"processed", "no_change"}}
                for item in occurrences:
                    detail = {"id": item.get("id"), "page": item["page"],
                              "roi": item.get("box_pixels"),
                              "current_filter": "Artístico", "requested_filter": "Artístico",
                              "status": item["status"]}
                    if item["status"] in {"pending", "failed"} and item["page"] in completed_pages:
                        detail["execution_blocked"] = True
                        detail["execution_block_reason"] = "Página já contém Artístico processado; autoria incremental indisponível."
                    if item["status"] in {"pending", "failed"} and item["page"] not in completed_pages:
                        if item["page"] not in restored_blocks:
                            try:
                                restored_blocks[item["page"]] = restored_block_reason(
                                    manga, provider, folder.name, item["page"])
                            except (OSError, ValueError, TypeError, KeyError) as exc:
                                restored_blocks[item["page"]] = str(exc)
                        if restored_blocks[item["page"]]:
                            detail["execution_blocked"] = True
                            detail["execution_block_reason"] = restored_blocks[item["page"]]
                    preview = _styled_preview(manga, provider, folder.name, item, previews)
                    if preview:
                        detail["preview"] = preview
                    if item["status"] in {"processed", "no_change"}:
                        try:
                            history = occurrence_input(manga, folder.name, item["page"],
                                                       item["id"], item["box_pixels"])
                            filt = (history["occurrence"].get("filter") or {}).get("algorithm")
                            if isinstance(filt, str):
                                detail["current_filter"] = filt
                                detail["requested_filter"] = filt
                            _record, current, _digest = read_final_page(
                                manga, folder.name, item["page"])
                            from central_v2.backend.orchestration.textoff_special.artifacts import sha256
                            detail["expected_sha256"] = sha256(current)
                        except (OSError, ValueError, TypeError, KeyError) as exc:
                            detail["reexecution_blocked"] = True
                            detail["reexecution_block_reason"] = str(exc)
                    available_occurrences.append(detail)
                eligible = [item for item in available_occurrences
                            if item["status"] in {"processed", "no_change"}]
                reexecution_blocked = not any(not item.get("reexecution_blocked")
                                              for item in eligible)
                reexecution_block_reason = next((item.get("reexecution_block_reason")
                    for item in eligible if item.get("reexecution_blocked")), None)
                if not eligible:
                    reexecution_block_reason = "Nenhuma ocorrência Artístico processada com autoria verificável."
            else:
                previews = {}
                for item in occurrences:
                    page = item["page"]
                    detail = {"id": item.get("id"), "page": page,
                              "roi": item.get("box_pixels"), "status": item["status"]}
                    preview = _page_preview(manga, folder.name, page, previews)
                    if preview:
                        detail["preview"] = preview
                    available_occurrences.append(detail)
            reviewable = (status in {"processed", "no_change"} if treatment == "degrade"
                          else bool(states & {"processed", "no_change"}))
            if treatment in {"degrade", "gradiente_suave", "estilizado"} and reviewable:
                try:
                    resolver = {"degrade": review_pairs, "gradiente_suave": smooth_review_pairs,
                                "estilizado": styled_review_pairs}[treatment]
                    review_available = bool(resolver(manga, provider, folder.name))
                except (OSError, ValueError, TypeError, KeyError):
                    pass
            chapters.append({"chapter": folder.name, "pages": pages,
                             "page_count": len(pages), "occurrence_count": len(occurrences),
                             "status": status, "statuses": sorted(states),
                             "review_available": review_available,
                             "reexecution_blocked": reexecution_blocked,
                             "reexecution_block_reason": reexecution_block_reason,
                             "occurrences": available_occurrences})
    return {"treatment": treatment, "chapters": chapters,
            "summary": {"chapters": len(chapters),
                        "pages": sum(row["page_count"] for row in chapters),
                        "occurrences": sum(row["occurrence_count"] for row in chapters)}}
