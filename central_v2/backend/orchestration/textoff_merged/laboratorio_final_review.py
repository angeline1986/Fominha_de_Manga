"""Read-only, versioned comparison of a Laboratory result with the final page."""
import hashlib
import json
from pathlib import Path
from urllib.parse import urlencode

from central_v2.backend.state.catalog import build_catalog
from central_v2.backend.state.manga_state import resolve_manga
from .final_consolidated import read_final_page
from .laboratorio_final_candidate import candidate, image_size

IMAGE_ROUTE = "/api/textoff/laboratorio/final/image"
FIELDS = ("provider", "manga", "chapter", "page", "treatment", "run_id")


def inspect(payload: dict, output_root: Path) -> dict:
    if not isinstance(payload, dict) or set(payload) != set(FIELDS):
        raise ValueError("Proposta do Laboratório inválida.")
    if any(not isinstance(payload[key], str) or not payload[key]
           or len(payload[key]) > 240 for key in FIELDS):
        raise ValueError("Identificação da proposta inválida.")
    provider, name = payload["provider"], payload["manga"]
    chapter, page = payload["chapter"], payload["page"]
    if (Path(chapter).name != chapter or chapter in {".", ".."}
            or Path(page).name != page or page in {".", ".."}):
        raise ValueError("Capítulo ou página inválidos.")
    if name not in build_catalog(output_root).get(provider, []):
        raise ValueError("Obra fora do catálogo.")
    manga = resolve_manga(output_root, provider, name).resolve()
    proposal = candidate(manga, chapter, page, payload["treatment"],
                         payload["run_id"], output_root)
    current_row, current_path, manifest_hash = read_final_page(manga, chapter, page)
    size = image_size(proposal["path"])
    if size != image_size(current_path):
        raise ValueError("Dimensões diferentes da página no Consolidado Final.")
    binding = {**payload, "candidate_sha256": proposal["sha256"],
               "current_sha256": current_row["sha256"],
               "final_manifest_sha256": manifest_hash}
    version = hashlib.sha256(json.dumps(binding, sort_keys=True).encode()).hexdigest()
    query = {**payload, "version": version}
    return {"version": version, "provider": provider, "manga": name,
            "chapter": chapter, "page": page, "treatment": proposal["treatment"],
            "run_id": proposal["run_id"], "artifact": proposal["artifact"],
            "source_sha256": proposal["source_sha256"],
            "candidate_sha256": proposal["sha256"],
            "current_sha256": current_row["sha256"],
            "current_origin": current_row.get("origin"),
            "final_manifest_sha256": manifest_hash, "width": size[0],
            "height": size[1],
            "current_image_url": IMAGE_ROUTE + "?" + urlencode({**query, "side": "current"}),
            "candidate_image_url": IMAGE_ROUTE + "?" + urlencode({**query, "side": "candidate"})}


def review_image(query: dict, output_root: Path) -> bytes:
    payload = {key: (query.get(key) or [""])[0] for key in FIELDS}
    expected = (query.get("version") or [""])[0]
    side = (query.get("side") or [""])[0]
    if side not in {"current", "candidate"} or not expected:
        raise ValueError("Prévia inválida.")
    reviewed = inspect(payload, output_root)
    if reviewed["version"] != expected:
        raise ValueError("Proposta obsoleta; compare as imagens novamente.")
    manga = resolve_manga(output_root, payload["provider"], payload["manga"]).resolve()
    current_row, current_path, manifest_hash = read_final_page(
        manga, payload["chapter"], payload["page"])
    if (manifest_hash != reviewed["final_manifest_sha256"]
            or current_row["sha256"] != reviewed["current_sha256"]):
        raise ValueError("Consolidado Final mudou; compare as imagens novamente.")
    if side == "current":
        path = current_path
        digest = reviewed["current_sha256"]
    else:
        selected = candidate(manga, payload["chapter"], payload["page"],
                             payload["treatment"], payload["run_id"], output_root)
        path, digest = selected["path"], reviewed["candidate_sha256"]
    content = path.read_bytes()
    if hashlib.sha256(content).hexdigest() != digest:
        raise ValueError("Imagem mudou durante a leitura.")
    return content
