"""Read-only local folder browser used by Central V2 export destination picker."""
import json
import os
from pathlib import Path

from central_v2.backend.routes.response import RouteResponse
from processamento.exportacao.exportador import display_path


def response(query):
    def reply(status, obj):
        return RouteResponse(status, json.dumps(obj, ensure_ascii=False).encode("utf-8"))
    try:
        raw = (query.get("path") or [""])[0]
        if not isinstance(raw, str) or len(raw) > 4096 or "\x00" in raw:
            raise ValueError("Caminho inválido.")
        home = Path.home().resolve()
        volumes = Path("/Volumes")
        roots = [home] + ([volumes.resolve()] if volumes.is_dir() else [])
        path = Path(raw).expanduser().resolve() if raw else home
        if not any(path == root or path.is_relative_to(root) for root in roots):
            raise ValueError("Selecione uma pasta dentro do usuário ou de /Volumes.")
        if not path.is_dir():
            raise ValueError("A pasta não existe.")
        parent = str(path.parent) if path not in roots else ""
        directories = []
        for entry in sorted(path.iterdir(), key=lambda p: p.name.casefold()):
            if entry.name.startswith(".") or entry.is_symlink() or not entry.is_dir():
                continue
            target = entry.resolve()
            if any(target == root or target.is_relative_to(root) for root in roots):
                directories.append({"name": entry.name, "path": str(target)})
            if len(directories) >= 300:
                break
        if path == home and volumes.is_dir():
            directories.insert(0, {"name": "Volumes (discos externos)", "path": str(volumes.resolve())})
        return reply(200, {"path": str(path), "display": display_path(path),
                           "parent": parent, "writable": os.access(path, os.W_OK),
                           "directories": directories})
    except (ValueError, OSError) as exc:
        return reply(400, {"error": str(exc)})

# Resolve the user's configured Google Drive destination without assuming a mount name.
DEFAULT_PARTS = ("03_Novel", "01_MANGA", "Staff_Berry")


def default_destination_response():
    def reply(status, payload):
        return RouteResponse(status, json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    home = Path.home()
    roots = []
    cloud = home / "Library" / "CloudStorage"
    if cloud.is_dir():
        roots.extend(sorted(cloud.glob("GoogleDrive-*")))
    volumes = Path("/Volumes")
    if volumes.is_dir():
        roots.extend(sorted(p for p in volumes.iterdir() if "google" in p.name.casefold()))
    for root in roots:
        for drive_root in (root / "Meu Drive", root / "My Drive", root):
            candidate = drive_root.joinpath(*DEFAULT_PARTS)
            try:
                resolved = candidate.resolve(strict=True)
                if resolved.is_dir() and os.access(resolved, os.W_OK):
                    return reply(200, {
                        "available": True, "path": str(resolved),
                        "display": "Meu Drive/" + "/".join(DEFAULT_PARTS),
                    })
            except OSError:
                continue
    return reply(200, {
        "available": False,
        "path": "",
        "display": "Meu Drive/" + "/".join(DEFAULT_PARTS),
        "warning": "Pasta padrão não encontrada ou sem permissão de gravação. Escolha o destino manualmente.",
    })
