"""Read chapter worklists from the persisted Special Treatments projection."""
from __future__ import annotations

import json
from pathlib import Path

from central_v2.backend.state.sorting import natural_sort_key

from .special_treatments_manifest import MANIFEST_NAME, SCHEMA, STATUSES, TREATMENTS
from .stages import stage_root
from .special_degrade_review import review_pairs
from .special_smooth_review import review_pairs as smooth_review_pairs


def query_special_treatments(manga: Path, provider: str, treatment: str) -> dict:
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
            reviewable = (status in {"processed", "no_change"} if treatment == "degrade"
                          else bool(states & {"processed", "no_change"}))
            if treatment in {"degrade", "gradiente_suave"} and reviewable:
                try:
                    resolver = review_pairs if treatment == "degrade" else smooth_review_pairs
                    review_available = bool(resolver(manga, provider, folder.name))
                except (OSError, ValueError, TypeError, KeyError):
                    pass
            chapters.append({"chapter": folder.name, "pages": pages,
                             "page_count": len(pages), "occurrence_count": len(occurrences),
                             "status": status, "statuses": sorted(states),
                             "review_available": review_available})
    return {"treatment": treatment, "chapters": chapters,
            "summary": {"chapters": len(chapters),
                        "pages": sum(row["page_count"] for row in chapters),
                        "occurrences": sum(row["occurrence_count"] for row in chapters)}}
