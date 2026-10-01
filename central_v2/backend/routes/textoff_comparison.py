"""Read-only Auto-Cleaner comparison endpoints."""
import mimetypes
from pathlib import Path

from .response import RouteResponse
from .textoff_merged import _context, _json, _value
from central_v2.backend.state.manga_state import resolve_manga
from central_v2.backend.orchestration.textoff_merged.comparison import comparison_pairs, pair_version


def comparison_response(query: dict, output_root: Path, *, image=False) -> RouteResponse:
    try:
        provider, name = _context(query, output_root)
        manga = resolve_manga(output_root, provider, name)
        chapter, step = _value(query, "chapter"), _value(query, "step")
        pairs = comparison_pairs(manga, chapter, step)
        if not image:
            return RouteResponse(200, _json({
                "pages": [{"id": str(index), "name": pair["name"], "version": pair_version(pair)} for index, pair in enumerate(pairs)],
                "experimental": step in {"3", "4"},
            }))
        side, index = _value(query, "side"), _value(query, "page")
        if side not in {"before", "after"} or not isinstance(index, str) or not index.isdecimal():
            raise ValueError("Imagem de comparação inválida.")
        number = int(index)
        if number >= len(pairs):
            raise ValueError("Resultado indisponível ou desatualizado.")
        if _value(query, "version") != pair_version(pairs[number]):
            raise ValueError("Resultado alterado durante a comparação. Reabra a tela.")
        path = pairs[number][side]
        return RouteResponse(200, path.read_bytes(), mimetypes.guess_type(path.name)[0] or "image/png")
    except (ValueError, TypeError):
        return RouteResponse(404, _json({"error": "Comparação indisponível para este capítulo e passo."}))
    except OSError:
        return RouteResponse(500, _json({"error": "Não foi possível carregar a comparação."}))
