"""Read and write the self-contained final TextOff chapter manifest."""
import json
from pathlib import Path

from central_v2.backend.orchestration.textoff_special.artifacts import sha256

SCHEMA = "textoff_consolidado_final_manifest_v1"
MANIFEST = "final-manifest.json"


def read_manifest(path, manga, chapter):
    payload = json.loads(path.read_text(encoding="utf-8"))
    if (payload.get("schema") != SCHEMA or payload.get("version") != 1
            or payload.get("provider") != Path(manga).parent.name
            or payload.get("manga") != Path(manga).name or payload.get("chapter") != chapter
            or not isinstance(payload.get("pages"), dict)):
        raise ValueError("Manifesto do Consolidado Final incompatível.")
    folder = path.parent.parent.resolve()
    for page, row in payload["pages"].items():
        image = (folder / page).resolve()
        if (not isinstance(row, dict) or row.get("page") != page or row.get("artifact") != page
                or Path(page).name != page or not image.is_relative_to(folder)
                or not image.is_file() or sha256(image) != row.get("sha256")):
            raise ValueError(f"Página final inválida: {page}.")
    return payload


def write_manifest(folder, payload):
    path = folder / "json" / MANIFEST
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
