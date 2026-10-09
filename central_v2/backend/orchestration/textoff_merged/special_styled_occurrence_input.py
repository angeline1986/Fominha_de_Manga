"""Resolve one Artístico occurrence from persisted, hash-verified authorship."""
import json
from pathlib import Path

from central_v2.backend.orchestration.textoff_special.artifacts import sha256

from .special_styled_authorship import verified
from .special_styled_input import historical_input


def occurrence_input(manga: Path, chapter: str, page: str,
                     identity: str, roi: dict) -> dict:
    source = historical_input(manga, chapter, page)
    manifest = source.get("art_manifest")
    if not manifest:
        raise ValueError("Histórico legado Artístico sem autoria por ocorrência.")
    folder = Path(manifest).parent.parent.resolve()
    payload = json.loads(Path(manifest).read_text(encoding="utf-8"))
    record = (payload.get("pages") or {}).get(page)
    if (not isinstance(record, dict) or identity not in record.get("occurrence_ids", [])
            or record["rois"][record["occurrence_ids"].index(identity)] != roi):
        raise ValueError("Ocorrência Artístico ausente ou ROI histórica divergente.")
    proof = (record.get("occurrences") or {}).get(identity)
    masks = verified(folder, proof, identity, roi, source["sha256"])
    if sha256(Path(manifest)) != source["art_manifest_sha256"]:
        raise ValueError("Manifesto Artístico mudou durante validação da autoria.")
    source["occurrence"] = {"id": identity, "roi": roi,
        "filter": proof.get("filter"),
        "mask_path": str(masks["changed"]), "mask_sha256": sha256(masks["changed"]),
        "write_mask_path": str(masks["write"]),
        "write_mask_sha256": sha256(masks["write"]),
        "other_masks": []}
    for other in record["occurrence_ids"]:
        if other == identity:
            continue
        other_roi = record["rois"][record["occurrence_ids"].index(other)]
        other_proof = verified(folder, (record.get("occurrences") or {}).get(other),
                               other, other_roi, source["sha256"])
        source["occurrence"]["other_masks"].append({
            "id": other, "path": str(other_proof["write"]),
            "sha256": sha256(other_proof["write"])})
    source["dependencies"] = record.get("dependencies", [])
    return source
