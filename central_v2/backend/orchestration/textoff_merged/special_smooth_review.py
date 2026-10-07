"""Resolve hash-verified historical Suave pairs from PINCEL_SUAVE."""
from __future__ import annotations

import hashlib
import json
import mimetypes
from pathlib import Path

from central_v2.backend.orchestration.textoff_special.artifacts import sha256
from central_v2.backend.orchestration.textoff_special.catalog import treatment_for

from .artifact_paths import artifact_file, artifact_ref
from .comparison import pair_version
from .stages import LEVEL1, LEVEL2, stage_chapter

STAGE = "PINCEL_SUAVE"
MANIFEST = "suave-manifest.json"
SCHEMA = "textoff_pincel_suave_manifest_v1"


def review_pairs(manga: Path, provider: str, chapter: str) -> list[dict]:
    manga = Path(manga).resolve()
    folder = stage_chapter(manga, STAGE, chapter, read_legacy=False).resolve()
    if not chapter or Path(chapter).name != chapter or not folder.is_relative_to(manga):
        raise ValueError("Capítulo Suave inválido.")
    manifest = folder / artifact_ref("json", MANIFEST)
    if not manifest.resolve().is_relative_to(folder):
        raise ValueError("Manifesto Suave fora do estágio.")
    manifest_hash = sha256(manifest)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    if (payload.get("schema") != SCHEMA or payload.get("version") != 1
            or payload.get("provider") != provider or payload.get("manga") != manga.name
            or payload.get("chapter") != chapter or payload.get("treatment") != "gradiente_suave"
            or payload.get("algorithm") != treatment_for("gradiente_suave").algorithm
            or not isinstance(payload.get("pages"), dict)):
        raise ValueError("Manifesto persistente Suave inválido.")
    pairs = []
    for page, row in sorted(payload["pages"].items()):
        if (not isinstance(page, str) or not page or Path(page).name != page
                or not isinstance(row, dict) or row.get("page") != page
                or not _identity(row, provider, manga, chapter)):
            raise ValueError("Página persistida Suave inválida.")
        if row.get("status") not in {"processed", "no_change"}:
            continue
        before, input_hash = _historical_input(manga, chapter, page, row)
        output_row = row.get("output")
        expected_output = artifact_ref("clean", Path(page).stem + "_suave.png")
        output_ref = output_row.get("artifact") if isinstance(output_row, dict) else None
        after = artifact_file(folder, output_ref, "clean")
        if (not isinstance(output_row, dict) or output_row.get("artifact") != expected_output
                or after is None or not after.resolve().is_relative_to(folder / "clean")
                or sha256(after) != output_row.get("sha256")):
            raise ValueError(f"Output Suave divergente: {page}.")
        pairs.append({"name": page, "before": before, "after": after,
                      "input_sha256": input_hash, "output_sha256": output_row["sha256"],
                      "occurrence_ids": row.get("occurrence_ids", []), "rois": row.get("rois", []),
                      "selected_from": row.get("selected_from"), "run_id": row.get("run_id")})
    if sha256(manifest) != manifest_hash:
        raise ValueError("Manifesto Suave mudou durante a leitura.")
    return pairs


def _identity(row, provider, manga, chapter):
    return (row.get("provider") == provider and row.get("manga") == manga.name
            and row.get("chapter") == chapter and row.get("treatment") == "gradiente_suave")


def _historical_input(manga, chapter, page, row):
    source, consolidated = row.get("input"), row.get("consolidated_manifest")
    if not isinstance(source, dict):
        raise ValueError("Entrada histórica Suave ausente.")
    snapshot = row.get("input_artifact") or {}
    reference = snapshot.get("artifact")
    if isinstance(reference, str):
        folder = stage_chapter(manga, "PINCEL_SUAVE", chapter, read_legacy=False).resolve()
        relative = Path(reference)
        before = (folder / relative).resolve()
        if (relative.is_absolute() or ".." in relative.parts or len(relative.parts) != 3
                or relative.parts[0] != "input" or not before.is_relative_to(folder)
                or not before.is_file() or snapshot.get("sha256") != source.get("sha256")
                or sha256(before) != source.get("sha256")):
            raise ValueError(f"Snapshot de entrada Suave divergente: {page}.")
        return before, source["sha256"]
    if not isinstance(consolidated, dict):
        raise ValueError("Manifesto Consolidado histórico Suave ausente.")
    before = Path(source.get("path", "")).resolve()
    manifest_path = Path(consolidated.get("path", "")).resolve()
    expected_manifest = (stage_chapter(manga, "TO_MERGED_CONSOLIDADO", chapter, read_legacy=False)
                         / artifact_ref("json", "clean-manifest.json")).resolve()
    if (not before.is_relative_to(manga) or not before.is_file() or before.suffix.lower() != ".png"
            or not expected_manifest.is_relative_to(manga)
            or manifest_path != expected_manifest or not manifest_path.is_file()
            or sha256(manifest_path) != consolidated.get("sha256")
            or sha256(before) != source.get("sha256")):
        raise ValueError(f"Input Consolidado Suave divergente: {page}.")
    projection = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_ref = artifact_ref("clean", Path(page).stem + "_clean" + Path(page).suffix)
    matches = [item for item in projection.get("selections", [])
               if isinstance(item, dict) and item.get("source") == page]
    if (len(matches) != 1 or matches[0].get("artifact") != expected_ref
            or matches[0].get("selected_from") != row.get("selected_from")
            or matches[0].get("sha256") != source["sha256"]
            or row.get("selected_from") not in {LEVEL1, LEVEL2}):
        raise ValueError(f"Referência Consolidada Suave divergente: {page}.")
    selected = artifact_file(stage_chapter(manga, row["selected_from"], chapter), expected_ref, "clean")
    if selected is None or selected.resolve() != before:
        raise ValueError(f"Imagem de entrada histórica Suave divergente: {page}.")
    return before, source["sha256"]


def suave_comparison_response(query, output_root, *, image=False):
    from central_v2.backend.routes.response import RouteResponse
    from central_v2.backend.routes.textoff_merged import _context, _json, _value
    from central_v2.backend.state.manga_state import resolve_manga

    try:
        provider, name = _context(query, output_root)
        chapter = _value(query, "chapter")
        pairs = review_pairs(resolve_manga(output_root, provider, name), provider, chapter)
        if not pairs:
            raise ValueError("Nenhuma página Suave revisável.")
        if not image:
            pages = [{"id": str(index), "name": pair["name"], "version": pair_version(pair),
                      "occurrence_ids": pair["occurrence_ids"], "rois": pair["rois"],
                      "input_sha256": pair["input_sha256"], "output_sha256": pair["output_sha256"]}
                     for index, pair in enumerate(pairs)]
            return RouteResponse(200, _json({"pages": pages, "experimental": False}))
        side, index, version = (_value(query, key) for key in ("side", "page", "version"))
        if side not in {"before", "after"} or not index.isdecimal():
            raise ValueError("Imagem Suave inválida.")
        number = int(index)
        if number >= len(pairs) or version != pair_version(pairs[number]):
            raise ValueError("Comparação Suave desatualizada.")
        path = pairs[number][side]
        content = path.read_bytes()
        expected = pairs[number]["input_sha256" if side == "before" else "output_sha256"]
        if hashlib.sha256(content).hexdigest() != expected:
            raise ValueError("Imagem Suave mudou durante a leitura.")
        return RouteResponse(200, content, mimetypes.guess_type(path.name)[0] or "image/png")
    except (ValueError, TypeError, KeyError, OSError):
        return RouteResponse(404, _json({"error": "Resultado Suave ausente ou com hash divergente."}))
