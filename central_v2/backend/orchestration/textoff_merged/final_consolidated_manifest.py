"""Read and write the self-contained final TextOff chapter manifest."""
import json
from pathlib import Path

from central_v2.backend.orchestration.textoff_special.artifacts import sha256
from .stages import provider_name

SCHEMA = "textoff_consolidado_final_manifest_v1"
MANIFEST = "final-manifest.json"


def _read_payload(path, manga, chapter):
    payload = json.loads(path.read_text(encoding="utf-8"))
    if (payload.get("schema") != SCHEMA or payload.get("version") != 1
            or payload.get("provider") != provider_name(manga)
            or payload.get("manga") != Path(manga).name or payload.get("chapter") != chapter
            or not isinstance(payload.get("pages"), dict)):
        raise ValueError("Manifesto do Consolidado Final incompatível.")
    return payload


def _verify_page(folder, page, row):
    image = (folder / page).resolve()
    if (not isinstance(row, dict) or row.get("page") != page or row.get("artifact") != page
            or Path(page).name != page or not image.is_relative_to(folder)
            or not image.is_file() or sha256(image) != row.get("sha256")):
        raise ValueError(f"Página final inválida: {page}.")


def read_manifest(path, manga, chapter):
    payload = _read_payload(path, manga, chapter)
    folder = path.parent.parent.resolve()
    for page, row in payload["pages"].items():
        _verify_page(folder, page, row)
    return payload


def read_origin_pages(path, manga, chapter, origins):
    """Verify only current pages relevant to a read-only origin summary."""
    payload = _read_payload(path, manga, chapter)
    folder = path.parent.parent.resolve()
    rows = []
    for page, row in payload["pages"].items():
        if isinstance(row, dict) and row.get("origin") in origins:
            _verify_page(folder, page, row)
            rows.append(row)
    return rows


def write_manifest(folder, payload):
    path = folder / "json" / MANIFEST
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
