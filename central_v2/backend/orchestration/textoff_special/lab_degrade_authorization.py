"""Short lived, image-bound approval records for experimental Degradê."""
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
from pathlib import Path
import secrets

from .artifacts import read_json, sha256, write_json

SCHEMA = "textoff_laboratorio_degrade_authorization_v1"
TTL = timedelta(minutes=10)


def selections_digest(selections: list[dict]) -> str:
    encoded = json.dumps(selections, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def _intersects(bbox: list, selections: list[dict]) -> list[int]:
    x, y, width, height = bbox
    hits = []
    for index, roi in enumerate(selections, 1):
        if (x < roi["x"] + roi["width"] and roi["x"] < x + width
                and y < roi["y"] + roi["height"] and roi["y"] < y + height):
            hits.append(index)
    return hits


def component_id(source_hash: str, roi_hash: str, report_hash: str,
                 mask_hash: str, decision: dict) -> str:
    identity = {"source": source_hash, "rois": roi_hash, "report": report_hash,
                "mask": mask_hash, "component": decision["component"],
                "bbox": decision["bbox"], "area": decision["area"],
                "reason": decision["reason"]}
    encoded = json.dumps(identity, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def candidate_rows(request: dict, report_path: Path, mask_path: Path) -> tuple[list, dict]:
    report = read_json(report_path)
    pages = report.get("pages") or []
    if len(pages) != 1 or pages[0].get("source") != "source.png":
        raise ValueError("Relatório de classificação experimental inválido.")
    source_hash = request["source"]["sha256"]
    rois = request["selections"]
    report_hash, mask_hash = sha256(report_path), sha256(mask_path)
    roi_hash = selections_digest(rois)
    candidates = []
    for decision in pages[0].get("component_decisions", []):
        if decision.get("reason") != "transparent_balloon_deferred":
            continue
        bbox = decision.get("bbox")
        if not isinstance(bbox, list) or len(bbox) != 4:
            raise ValueError("Componente adiado sem geometria válida.")
        hits = _intersects(bbox, rois)
        if not hits:
            continue
        candidates.append({"id": component_id(source_hash, roi_hash, report_hash,
                            mask_hash, decision), "component": decision["component"],
                           "bbox": bbox, "area": decision["area"],
                           "roi_hits": hits, "reason": decision["reason"]})
    binding = {"source_sha256": source_hash, "selections_sha256": roi_hash,
               "report_sha256": report_hash, "raw_mask_sha256": mask_hash}
    return candidates, binding


def revalidate_worker(authorization: dict, source_hash: str, selections: list,
                     report_path: Path, raw_mask_hash: str) -> set[int]:
    """Bind worker candidates to its fresh classifier report and raw mask."""
    report_hash = sha256(report_path)
    roi_hash = selections_digest(authorization.get("selections", []))
    if authorization.get("schema") != SCHEMA:
        raise ValueError("Autorização experimental inválida.")
    if authorization.get("source", {}).get("sha256") != source_hash:
        raise ValueError("PROPOSTA_OBSOLETA: hash da imagem mudou.")
    if authorization.get("selections") != selections:
        raise ValueError("PROPOSTA_OBSOLETA: ROIs mudaram.")
    expected = {"source_sha256": source_hash, "selections_sha256": roi_hash,
                "report_sha256": report_hash, "raw_mask_sha256": raw_mask_hash}
    if authorization.get("binding") != expected:
        mismatches = [key for key, value in expected.items()
                      if authorization.get("binding", {}).get(key) != value]
        raise ValueError("PROPOSTA_OBSOLETA: classificação ou máscara mudou ("
                         + ", ".join(mismatches) + ").")
    report = read_json(report_path)
    pages = report.get("pages") or []
    if len(pages) != 1 or pages[0].get("source") != "source.png":
        raise ValueError("Relatório de classificação experimental inválido.")
    decisions = pages[0].get("component_decisions", [])
    by_id = {}
    for decision in decisions:
        if decision.get("reason") == "transparent_balloon_deferred":
            identity = component_id(source_hash, roi_hash, report_hash,
                                    raw_mask_hash, decision)
            by_id[identity] = decision["component"]
    selected = [row.get("id") for row in authorization.get("components", [])]
    if (not selected or len(selected) != len(set(selected))
            or any(identity not in by_id for identity in selected)):
        raise ValueError("PROPOSTA_OBSOLETA: componente não revalidado.")
    return {by_id[identity] for identity in selected}


def issue(folder: Path, run_id: str, request: dict, candidates: list,
          binding: dict) -> tuple[str, dict]:
    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    record = {"schema": SCHEMA, "run_id": run_id,
              "token_sha256": hashlib.sha256(token.encode()).hexdigest(),
              "status": "pending", "created_at": now.isoformat(),
              "expires_at": (now + TTL).isoformat(), "source": request["source"],
              "selections": request["selections"], "binding": binding,
              "candidates": candidates}
    manifest = read_json(folder / "manifest.json")
    if manifest.get("run_id") != run_id:
        raise ValueError("Manifesto da proposta experimental divergente.")
    manifest["laboratory_authorization_proposal"] = record
    write_json(folder / "manifest.json", manifest)
    return token, record


def load_pending(folder: Path, token: str) -> dict:
    manifest = read_json(folder / "manifest.json")
    record = manifest.get("laboratory_authorization_proposal") or {}
    digest = hashlib.sha256(token.encode()).hexdigest()
    if (record.get("run_id") != manifest.get("run_id")
            or record.get("schema") != SCHEMA or record.get("status") != "pending"
            or not hmac.compare_digest(record.get("token_sha256", ""), digest)):
        raise ValueError("Proposta inválida ou já consumida.")
    if datetime.now(timezone.utc) > datetime.fromisoformat(record["expires_at"]):
        record["status"] = "expired"
        manifest["laboratory_authorization_proposal"] = record
        write_json(folder / "manifest.json", manifest)
        raise ValueError("Proposta de autorização expirada; execute novamente.")
    return record


def consume(folder: Path, record: dict, selected: list[str]) -> dict:
    manifest = read_json(folder / "manifest.json")
    current = manifest.get("laboratory_authorization_proposal") or {}
    if (current.get("run_id") != manifest.get("run_id")
            or current.get("status") != "pending"
            or current.get("token_sha256") != record.get("token_sha256")):
        raise ValueError("Proposta inválida ou já consumida.")
    record = current
    available = {item["id"]: item for item in record["candidates"]}
    if (not selected or len(selected) != len(set(selected))
            or any(item not in available for item in selected)):
        raise ValueError("Selecione componentes presentes na proposta.")
    record["status"] = "consumed"
    record["consumed_at"] = datetime.now(timezone.utc).isoformat()
    record["selected_components"] = [available[item] for item in selected]
    manifest["laboratory_authorization_proposal"] = record
    write_json(folder / "manifest.json", manifest)
    return {"schema": SCHEMA, "proposal_run_id": record["run_id"],
            "source": record["source"], "selections": record["selections"],
            "binding": record["binding"],
            "components": record["selected_components"]}
