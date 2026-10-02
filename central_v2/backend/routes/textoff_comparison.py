"""Read-only Auto-Cleaner comparison endpoints."""
import mimetypes
from pathlib import Path

from .response import RouteResponse
from .textoff_merged import _context, _json, _value
from central_v2.backend.state.manga_state import resolve_manga
from central_v2.backend.orchestration.textoff_merged.comparison import comparison_pairs, pair_version
from central_v2.backend.orchestration.textoff_merged.residue_occurrences import (
    MANIFEST_NAME, occurrence_counts_for_step, read_manifest,
)
from central_v2.backend.orchestration.textoff_merged.stages import stage_chapter


def comparison_response(query: dict, output_root: Path, *, image=False) -> RouteResponse:
    try:
        provider, name = _context(query, output_root)
        manga = resolve_manga(output_root, provider, name)
        chapter, step = _value(query, "chapter"), _value(query, "step")
        pairs = comparison_pairs(manga, chapter, step)
        if not image:
            manifest_path = stage_chapter(manga, "RESIDUE_OCCURRENCES", chapter,
                                          read_legacy=False) / MANIFEST_NAME
            document = {"provider": provider, "obra": name, "capitulo": chapter}
            counts = occurrence_counts_for_step(read_manifest(manifest_path, document), step)
            return RouteResponse(200, _json({
                "pages": [{"id": str(index), "name": pair["name"], "version": pair_version(pair),
                           "residue_occurrence_count": counts.get(pair["name"], 0)}
                          for index, pair in enumerate(pairs)],
                "experimental": step in {"3", "4"},
            }))
        side, index = _value(query, "side"), _value(query, "page")
        if side not in {"before", "after"} or not isinstance(index, str) or not index.isdecimal():
            raise ValueError("Imagem de comparação inválida.")
        number = int(index)
        version = _value(query, "version")
        pair = None
        if number < len(pairs) and version == pair_version(pairs[number]):
            pair = pairs[number]
        else:
            # A version is bound to the image pair and also tolerates clients
            # that number page IDs from 1 instead of 0.
            matches = [(ordinal, item) for ordinal, item in enumerate(pairs)
                       if version == pair_version(item)]
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
