"""Read only historically exact Degradê pairs from its persisted stage."""
from __future__ import annotations

import json
from pathlib import Path

from central_v2.backend.orchestration.textoff_special.artifacts import sha256

from .artifact_paths import artifact_ref
from .special_degrade_output import MANIFEST, SCHEMA, STAGE
from .stages import stage_chapter


def review_pairs(manga: Path, provider: str, chapter: str) -> list[dict]:
    manga = Path(manga).resolve()
    if not isinstance(chapter, str) or not chapter or Path(chapter).name != chapter:
        raise ValueError("Capítulo Degradê inválido.")
    folder = stage_chapter(manga, STAGE, chapter, read_legacy=False).resolve()
    if not folder.is_relative_to(manga):
        raise ValueError("Estágio Degradê fora da obra.")
    manifest = folder / artifact_ref("json", MANIFEST)
    manifest_hash = sha256(manifest)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    if (payload.get("schema") != SCHEMA or payload.get("version") != 1
            or payload.get("provider") != provider or payload.get("manga") != manga.name
            or payload.get("chapter") != chapter or payload.get("treatment") != "degrade"
            or not isinstance(payload.get("pages"), dict)):
        raise ValueError("Manifesto persistente de Degradê inválido.")
    pairs = []
    for page, row in sorted(payload["pages"].items()):
        if (not isinstance(page, str) or Path(page).name != page or not isinstance(row, dict)
                or row.get("page") != page or row.get("chapter") != chapter
                or row.get("provider") != provider or row.get("manga") != manga.name
                or row.get("treatment") != "degrade"):
            raise ValueError("Página persistida de Degradê inválida.")
        if row.get("status") not in {"processed", "no_change"}:
            continue
        if not isinstance(row.get("selected_from"), str):
            raise ValueError("Fonte persistida de Degradê inválida.")
        ids, rois = row.get("occurrence_ids"), row.get("rois")
        if (not isinstance(ids, list) or not ids or not all(isinstance(item, str) and item for item in ids)
                or not isinstance(rois, list) or len(rois) != len(ids)
                or not all(_valid_roi(box) for box in rois)
                or not isinstance(row.get("run_id"), str) or not row["run_id"].isalnum()):
            raise ValueError("Proveniência das ROIs Degradê inválida.")
        source, output = row.get("input"), row.get("output")
        if not isinstance(source, dict) or not isinstance(output, dict):
            raise ValueError("Artefatos Degradê ausentes.")
        before = _input_snapshot(folder, row, source)
        expected_output = artifact_ref("clean", Path(page).stem + "_degrade.png")
        if (not before.is_relative_to(manga) or not before.is_file()
                or before.suffix.lower() != ".png" or output.get("artifact") != expected_output):
            raise ValueError("Entrada ou saída persistida fora da obra.")
        after = (folder / expected_output).resolve()
        if (not after.is_relative_to(folder / "clean") or not after.is_file()
                or sha256(before) != source.get("sha256")
                or sha256(after) != output.get("sha256")):
            raise ValueError(f"Hash ou arquivo Degradê divergente: {page}.")
        pairs.append({"name": page, "before": before, "after": after,
                      "selected_from": row["selected_from"],
                      "input_sha256": source["sha256"], "output_sha256": output["sha256"],
                      "occurrence_ids": ids, "rois": rois, "run_id": row["run_id"]})
    if sha256(manifest) != manifest_hash:
        raise ValueError("Manifesto Degradê mudou durante a leitura.")
    return pairs


def _input_snapshot(folder, row, source):
    reference = row.get("input_artifact") or {}
    artifact = reference.get("artifact")
    if isinstance(artifact, str):
        relative = Path(artifact)
        candidate = (folder / relative).resolve()
        if (relative.is_absolute() or ".." in relative.parts
                or len(relative.parts) != 3 or relative.parts[0] != "input"
                or not candidate.is_relative_to(folder) or not candidate.is_file()
                or reference.get("sha256") != source.get("sha256")):
            raise ValueError("Snapshot de entrada Degradê inválido.")
        return candidate
    return Path(source.get("path", "")).resolve()


def _valid_roi(box: object) -> bool:
    return (isinstance(box, dict) and all(type(box.get(key)) in {int, float}
            for key in ("x", "y", "width", "height"))
            and box["x"] >= 0 and box["y"] >= 0
            and box["width"] > 0 and box["height"] > 0)
