"""Immutable Check images captured at the first saved review decision."""
import hashlib
import json
import os
from pathlib import Path
import tempfile

from .auto_cleaner_check_manifest import manifest_path


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def freeze_check_images(manga: Path, chapter: str, pairs: list[dict]) -> dict:
    """Capture every reviewed image before downstream processing changes the Consolidado."""
    folder = manifest_path(manga, chapter).parent / "images"
    folder.mkdir(parents=True, exist_ok=True)
    saved = {}
    for pair in pairs:
        name = pair["name"]
        if (not isinstance(name, str) or not name or name in {".", ".."}
                or Path(name).name != name or "\\" in name):
            raise ValueError("Nome inválido de imagem histórica do Check.")
        target = folder / name
        data = Path(pair["after"]).read_bytes()
        digest = _sha(data)
        if target.exists():
            if _sha(target.read_bytes()) != digest:
                raise ValueError("Snapshot histórico existente difere da fonte do Check.")
        else:
            descriptor, temp_name = tempfile.mkstemp(prefix=".check-", dir=folder)
            try:
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write(data)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temp_name, target)
            finally:
                Path(temp_name).unlink(missing_ok=True)
        saved[name] = {"file": f"images/{name}", "sha256": digest}
    return saved


def check_image(manga: Path, chapter: str, name: str, fallback: Path) -> Path:
    """Use the frozen image when available; legacy experimental Check uses Level I."""
    path = manifest_path(manga, chapter)
    if not path.is_file():
        return fallback
    manifest = json.loads(path.read_text(encoding="utf-8"))
    snapshots = manifest.get("image_snapshot")
    if snapshots is None:
        return fallback  # Unmigrated experimental manifest
    entry = snapshots.get(name) if isinstance(snapshots, dict) else None
    if not isinstance(entry, dict) or entry.get("file") != f"images/{name}":
        raise ValueError("Snapshot histórico do Check incompleto.")
    target = path.parent / "images" / name
    if not target.is_file() or _sha(target.read_bytes()) != entry.get("sha256"):
        raise ValueError("Snapshot histórico do Check ausente ou divergente.")
    return target
