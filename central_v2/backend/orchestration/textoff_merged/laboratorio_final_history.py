"""List verified final-page revisions and serve version-bound previews."""
import hashlib
import json
from pathlib import Path
from urllib.parse import urlencode

from central_v2.backend.orchestration.textoff_special.artifacts import sha256
from central_v2.backend.state.catalog import build_catalog
from central_v2.backend.state.manga_state import resolve_manga
from .final_consolidated import _read_final_page, final_manifest_path
from .final_consolidated_manifest import read_manifest
from .special_styled_transaction import transaction_lock

FIELDS = ("provider", "manga", "chapter", "page")
IMAGE_ROUTE = "/api/textoff/laboratorio/final/history/image"


def _identity(payload, output_root):
    if (not isinstance(payload, dict) or set(payload) != set(FIELDS)
            or any(not isinstance(payload[key], str) or not payload[key]
                   or len(payload[key]) > 240 for key in FIELDS)):
        raise ValueError("Identificação da página inválida.")
    for key in ("chapter", "page"):
        value = payload[key]
        if Path(value).name != value or value in {".", ".."}:
            raise ValueError("Capítulo ou página inválidos.")
    if payload["manga"] not in build_catalog(output_root).get(payload["provider"], []):
        raise ValueError("Obra fora do catálogo.")
    return resolve_manga(output_root, payload["provider"], payload["manga"]).resolve()


def archived_path(folder, entry, page):
    old = entry.get("superseded")
    digest = entry.get("archived_sha256")
    artifact = entry.get("archived_artifact")
    if (entry.get("page") != page or not isinstance(old, dict)
            or old.get("page") != page or old.get("artifact") != page
            or not isinstance(digest, str) or len(digest) != 64
            or old.get("sha256") != digest or not isinstance(artifact, str)):
        return None
    relative = Path(artifact)
    if (relative.is_absolute() or ".." in relative.parts or len(relative.parts) != 3
            or relative.parts != ("history", digest, page)):
        return None
    path = (folder / relative).resolve()
    if not path.is_relative_to(folder) or not path.is_file() or sha256(path) != digest:
        return None
    return path


def inspect(payload: dict, output_root: Path) -> dict:
    manga = _identity(payload, output_root)
    chapter, page = payload["chapter"], payload["page"]
    with transaction_lock(manga):
        current, _image, manifest_hash = _read_final_page(manga, chapter, page)
        manifest = read_manifest(final_manifest_path(manga, chapter), manga, chapter)
        folder = final_manifest_path(manga, chapter).parent.parent.resolve()
        version = hashlib.sha256(json.dumps({**payload, "manifest": manifest_hash,
            "page_sha256": current["sha256"]}, sort_keys=True).encode()).hexdigest()
        query = {**payload, "version": version}
        revisions = []
        for index, entry in reversed(list(enumerate(manifest.get("history", [])))):
            if not isinstance(entry, dict) or not archived_path(folder, entry, page):
                continue
            old = entry["superseded"]
            revision = hashlib.sha256(f"{index}:{entry['archived_sha256']}".encode()).hexdigest()
            revisions.append({"revision_id": revision, "sha256": old["sha256"],
                "origin": old.get("origin"), "treatment": old.get("treatment"),
                "run_id": old.get("run_id"), "superseded_at": entry.get("superseded_at"),
                "image_url": IMAGE_ROUTE + "?" + urlencode({**query,
                    "side": "historical", "revision_id": revision})})
        return {**payload, "version": version, "current": {
            "sha256": current["sha256"], "origin": current.get("origin"),
            "treatment": current.get("treatment"), "run_id": current.get("run_id")},
            "current_image_url": IMAGE_ROUTE + "?" + urlencode({**query, "side": "current"}),
            "revisions": revisions}


def revision_entry(payload, output_root, version, revision_id):
    history = inspect(payload, output_root)
    if history["version"] != version:
        raise ValueError("PROPOSTA_OBSOLETA: Consolidado Final mudou.")
    revision = next((row for row in history["revisions"]
                     if row["revision_id"] == revision_id), None)
    if revision is None:
        raise ValueError("Versão histórica indisponível.")
    manga = _identity(payload, output_root)
    manifest = read_manifest(final_manifest_path(manga, payload["chapter"]),
                             manga, payload["chapter"])
    folder = final_manifest_path(manga, payload["chapter"]).parent.parent.resolve()
    for index, entry in enumerate(manifest.get("history", [])):
        if not isinstance(entry, dict):
            continue
        digest = entry.get("archived_sha256")
        identity = hashlib.sha256(f"{index}:{digest}".encode()).hexdigest()
        if identity == revision_id:
            path = archived_path(folder, entry, payload["page"])
            if path and digest == revision["sha256"]:
                return history, entry, path
    raise ValueError("Versão histórica indisponível.")


def history_image(query: dict, output_root: Path) -> bytes:
    payload = {key: (query.get(key) or [""])[0] for key in FIELDS}
    version = (query.get("version") or [""])[0]
    side = (query.get("side") or [""])[0]
    revision_id = (query.get("revision_id") or [""])[0]
    if not version or side not in {"current", "historical"}:
        raise ValueError("Prévia histórica inválida.")
    if side == "historical":
        history, _entry, path = revision_entry(payload, output_root, version, revision_id)
        digest = next(row["sha256"] for row in history["revisions"]
                      if row["revision_id"] == revision_id)
    else:
        history = inspect(payload, output_root)
        if history["version"] != version:
            raise ValueError("PROPOSTA_OBSOLETA: Consolidado Final mudou.")
        manga = _identity(payload, output_root)
        _row, path, _hash = _read_final_page(manga, payload["chapter"], payload["page"])
        digest = history["current"]["sha256"]
    content = path.read_bytes()
    if hashlib.sha256(content).hexdigest() != digest:
        raise ValueError("Imagem mudou durante a leitura.")
    if inspect(payload, output_root)["version"] != version:
        raise ValueError("PROPOSTA_OBSOLETA: Consolidado Final mudou durante a leitura.")
    return content
