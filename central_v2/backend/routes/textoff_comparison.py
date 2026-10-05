"""Read-only Auto-Cleaner comparison endpoints."""
import mimetypes
from pathlib import Path

from .response import RouteResponse
from .textoff_merged import _context, _json, _value
from central_v2.backend.state.manga_state import resolve_manga
from central_v2.backend.orchestration.textoff_merged.comparison import (
    comparison_pairs, comparison_triplets, pair_version, triplet_version,
)
from central_v2.backend.orchestration.textoff_merged.residue_occurrences import (
    MANIFEST_NAME, occurrence_counts_for_step, read_manifest,
)
from central_v2.backend.orchestration.textoff_merged.stages import stage_chapter


def comparison_response(query: dict, output_root: Path, *, image=False) -> RouteResponse:
    try:
        provider, name = _context(query, output_root)
        manga = resolve_manga(output_root, provider, name)
        chapter, step = _value(query, "chapter"), _value(query, "step")
        triptych = _value(query, "layout") == "triptych" and step in {"1", "2"}
        pairs = comparison_triplets(manga, chapter) if triptych else comparison_pairs(manga, chapter, step)
        if not image:
            manifest_path = stage_chapter(manga, "RESIDUE_OCCURRENCES", chapter,
                                          read_legacy=False) / MANIFEST_NAME
            document = {"provider": provider, "obra": name, "capitulo": chapter}
            counts = occurrence_counts_for_step(read_manifest(manifest_path, document), step)
            return RouteResponse(200, _json({
                "pages": [_page_response(index, pair, counts, triptych)
                          for index, pair in enumerate(pairs)],
                "experimental": step in {"3", "4"},
            }))
        side, index = _value(query, "side"), _value(query, "page")
        allowed_sides = {"original", "level1", "level2"} if triptych else {"before", "after"}
        if side not in allowed_sides or not isinstance(index, str) or not index.isdecimal():
            raise ValueError("Imagem de comparação inválida.")
        number = int(index)
        version = _value(query, "version")
        pair = None
        version_for = triplet_version if triptych else pair_version
        if number < len(pairs) and version == version_for(pairs[number]):
            pair = pairs[number]
        else:
            # A version is bound to the image pair and also tolerates clients
            # that number page IDs from 1 instead of 0.
            matches = [(ordinal, item) for ordinal, item in enumerate(pairs)
                       if version == version_for(item)]
            if len(matches) != 1:
                raise ValueError("Resultado indisponível ou desatualizado.")
            ordinal, pair = matches[0]
            if number != ordinal + 1:
                raise ValueError("Resultado indisponível ou desatualizado.")
        path = pair[side]
        return RouteResponse(200, path.read_bytes(), mimetypes.guess_type(path.name)[0] or "image/png")
    except (ValueError, TypeError):
        return RouteResponse(404, _json({"error": "Comparação indisponível para este capítulo e passo."}))
    except OSError:
        return RouteResponse(500, _json({"error": "Não foi possível carregar a comparação."}))


def _page_response(index: int, page: dict, counts: dict, triptych: bool) -> dict:
    version = triplet_version(page) if triptych else pair_version(page)
    result = {"id": str(index), "name": page["name"], "version": version,
              "residue_occurrence_count": counts.get(page["name"], 0)}
    if triptych:
        result.update({"level2_status": page["level2_status"],
                       "level2_chapter_status": page["level2_chapter_status"]})
    return result
