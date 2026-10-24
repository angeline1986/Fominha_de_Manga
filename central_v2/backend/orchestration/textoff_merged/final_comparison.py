"""Resolve the verified final image for the four-stage quality audit."""
import hashlib
from pathlib import Path

from .comparison import comparison_triplets, triplet_version
from .final_consolidated import final_manifest_path
from .final_consolidated_manifest import read_manifest
from .special_styled_transaction import transaction_lock


def comparison_quads(manga: Path, chapter: str) -> list[dict]:
    pages = comparison_triplets(manga, chapter)
    if not pages:
        return pages
    with transaction_lock(manga):
        manifest_path = final_manifest_path(manga, chapter).resolve()
        folder = manifest_path.parent.parent
        if not folder.is_relative_to(manga.resolve()):
            raise ValueError("Consolidado Final fora da obra.")
        if not manifest_path.is_file():
            if folder.exists():
                raise OSError("Consolidado Final existente sem manifesto.")
            return [{**page, "final": None} for page in pages]
        manifest = read_manifest(manifest_path, manga, chapter)
        if set(manifest["pages"]) != {page["name"] for page in pages}:
            raise OSError("Consolidado Final incompleto para o capítulo.")
        return [{**page, "final": folder / page["name"]} for page in pages]


def quad_version(page: dict) -> str:
    final = page["final"]
    signature = triplet_version(page)
    if final is not None:
        info = final.stat()
        signature += f"|{final.resolve()}:{info.st_size}:{info.st_mtime_ns}"
    else:
        signature += "|final:unavailable"
    return hashlib.sha256(signature.encode()).hexdigest()
