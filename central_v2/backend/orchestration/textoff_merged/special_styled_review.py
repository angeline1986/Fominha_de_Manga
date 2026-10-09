"""Serve hash-verified historical Artístico input/output comparisons."""
import hashlib
import json
import mimetypes
from pathlib import Path

from central_v2.backend.orchestration.textoff_special.artifacts import sha256
from central_v2.backend.orchestration.textoff_special.catalog import treatment_for

from .artifact_paths import artifact_ref
from .comparison import pair_version
from .special_degrade_review import _valid_roi
from .special_styled_output import MANIFEST, SCHEMA, STAGE
from .stages import stage_chapter
from .special_styled_transaction import transaction_lock


def review_pairs(manga: Path, provider: str, chapter: str) -> list[dict]:
    manga = Path(manga).resolve()
    with transaction_lock(manga):
        return _review_pairs(manga, provider, chapter)


def _review_pairs(manga: Path, provider: str, chapter: str) -> list[dict]:
    manga = Path(manga).resolve()
    folder = stage_chapter(manga, STAGE, chapter, read_legacy=False).resolve()
    if not chapter or Path(chapter).name != chapter or not folder.is_relative_to(manga):
        raise ValueError("Capítulo Artístico inválido.")
    manifest = folder / artifact_ref("json", MANIFEST)
    manifest_hash = sha256(manifest)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    if (payload.get("schema") != SCHEMA or payload.get("version") != 1
            or payload.get("provider") != provider or payload.get("manga") != manga.name
            or payload.get("chapter") != chapter or payload.get("treatment") != "estilizado"
            or payload.get("algorithm") != treatment_for("estilizado").algorithm
            or not isinstance(payload.get("pages"), dict)):
        raise ValueError("Manifesto persistente Artístico inválido.")
    pairs = []
    for page, row in sorted(payload["pages"].items()):
        if not isinstance(row, dict) or row.get("page") != page or not _identity(row, provider, manga, chapter):
            raise ValueError("Página persistida Artístico inválida.")
        if row.get("status") not in {"processed", "no_change"}:
            continue
        ids, rois = row.get("occurrence_ids"), row.get("rois")
        if (not isinstance(ids, list) or not ids or not all(isinstance(item, str) and item for item in ids)
                or not isinstance(rois, list) or len(rois) != len(ids)
                or not all(_valid_roi(box) for box in rois)):
            raise ValueError("Proveniência das ROIs Artístico inválida.")
        source, output = row.get("input"), row.get("output")
        if not isinstance(source, dict) or not isinstance(output, dict):
            raise ValueError("Artefatos Artístico ausentes.")
        before = _input_snapshot(folder, row, source)
        expected = artifact_ref("clean", Path(page).stem + "_artistico.png")
        after = (folder / expected).resolve()
        if (not after.is_relative_to(folder / "clean") or not after.is_file()
                or output.get("artifact") != expected or sha256(before) != source.get("sha256")
                or sha256(after) != output.get("sha256")):
            raise ValueError(f"Hash ou arquivo Artístico divergente: {page}.")
        pairs.append({"name": page, "before": before, "after": after,
            "input_sha256": source["sha256"], "output_sha256": output["sha256"],
            "occurrence_ids": ids, "rois": rois, "selected_from": row["selected_from"],
            "run_id": row["run_id"]})
    if sha256(manifest) != manifest_hash:
        raise ValueError("Manifesto Artístico mudou durante a leitura.")
    return pairs


def _identity(row, provider, manga, chapter):
    return (row.get("provider") == provider and row.get("manga") == manga.name
            and row.get("chapter") == chapter and row.get("treatment") == "estilizado")


def _input_snapshot(folder, row, source):
    ref = (row.get("input_artifact") or {}).get("artifact")
    relative = Path(ref) if isinstance(ref, str) else Path()
    before = (folder / relative).resolve()
    if (not isinstance(ref, str) or relative.is_absolute() or ".." in relative.parts
            or len(relative.parts) != 3 or relative.parts[0] != "input"
            or not before.is_relative_to(folder) or not before.is_file()
            or (row.get("input_artifact") or {}).get("sha256") != source.get("sha256")):
        raise ValueError("Snapshot histórico Artístico inválido.")
    return before


def artistico_comparison_response(query, output_root, *, image=False):
    from central_v2.backend.routes.response import RouteResponse
    from central_v2.backend.routes.textoff_merged import _context, _json, _value
    from central_v2.backend.state.manga_state import resolve_manga

    try:
        provider, name = _context(query, output_root)
        pairs = review_pairs(resolve_manga(output_root, provider, name), provider,
                             _value(query, "chapter"))
        if not image:
            pages = [{"id": str(i), "name": row["name"], "version": pair_version(row),
                "occurrence_ids": row["occurrence_ids"], "rois": row["rois"],
                "input_sha256": row["input_sha256"], "output_sha256": row["output_sha256"]}
                for i, row in enumerate(pairs)]
            return RouteResponse(200, _json({"pages": pages, "experimental": False}))
        side, index, version = (_value(query, key) for key in ("side", "page", "version"))
        if side not in {"before", "after"} or not index.isdecimal():
            raise ValueError("Imagem Artístico inválida.")
        number = int(index)
        if number >= len(pairs) or version != pair_version(pairs[number]):
            raise ValueError("Comparação Artístico desatualizada.")
        pair = pairs[number]
        content = pair[side].read_bytes()
        expected = pair["input_sha256" if side == "before" else "output_sha256"]
        if hashlib.sha256(content).hexdigest() != expected:
            raise ValueError("Imagem Artístico mudou durante a leitura.")
        return RouteResponse(200, content, mimetypes.guess_type(pair[side].name)[0] or "image/png")
    except (ValueError, TypeError, KeyError, OSError):
        return RouteResponse(404, _json({"error": "Resultado Artístico ausente ou com hash divergente."}))
