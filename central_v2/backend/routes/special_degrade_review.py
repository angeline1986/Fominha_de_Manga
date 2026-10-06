"""Serve validated, read-only Degradê comparison pairs."""
import hashlib
import mimetypes
from pathlib import Path

from central_v2.backend.orchestration.textoff_merged.comparison import pair_version
from central_v2.backend.orchestration.textoff_merged.special_degrade_review import review_pairs
from central_v2.backend.state.manga_state import resolve_manga

from .response import RouteResponse
from .textoff_merged import _context, _json, _value


def degrade_comparison_response(query: dict, output_root: Path, *, image=False) -> RouteResponse:
    try:
        provider, name = _context(query, output_root)
        chapter = _value(query, "chapter")
        pairs = review_pairs(resolve_manga(output_root, provider, name), provider, chapter)
        if not pairs:
            raise ValueError("Nenhuma página Degradê revisável.")
        if not image:
            pages = [{"id": str(index), "name": pair["name"],
                      "version": pair_version(pair),
                      "residue_occurrence_count": len(pair["occurrence_ids"]),
                      "occurrence_ids": pair["occurrence_ids"], "rois": pair["rois"],
                      "selected_from": pair["selected_from"], "run_id": pair["run_id"],
                      "input_sha256": pair["input_sha256"],
                      "output_sha256": pair["output_sha256"]}
                     for index, pair in enumerate(pairs)]
            return RouteResponse(200, _json({"pages": pages, "experimental": False}))
        side, index, version = (_value(query, key) for key in ("side", "page", "version"))
        if side not in {"before", "after"} or not index.isdecimal():
            raise ValueError("Imagem Degradê inválida.")
        number = int(index)
        if number >= len(pairs) or version != pair_version(pairs[number]):
            raise ValueError("Comparação Degradê desatualizada.")
        path = pairs[number][side]
        content = path.read_bytes()
        expected = pairs[number]["input_sha256" if side == "before" else "output_sha256"]
        if hashlib.sha256(content).hexdigest() != expected:
            raise ValueError("Imagem Degradê mudou durante a leitura.")
        return RouteResponse(200, content, mimetypes.guess_type(path.name)[0] or "image/png")
    except (ValueError, TypeError, KeyError, OSError):
        return RouteResponse(404, _json({"error": "Resultado Degradê ausente ou com hash divergente."}))
