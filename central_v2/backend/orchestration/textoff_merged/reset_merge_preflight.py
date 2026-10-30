"""Read-only eligibility assessment for per-page MERGE reset."""
from hashlib import sha256
from pathlib import Path
import json
from central_v2.backend.state.work_layout import images_root

from central_v2.backend.orchestration.textoff_merged.manifests import _listing_merge_artifacts
from central_v2.backend.orchestration.textoff_merged.auto_cleaner_check_manifest import manifest_path
from central_v2.backend.orchestration.textoff_merged.final_consolidated import final_manifest_path
from central_v2.backend.orchestration.textoff_merged.final_consolidated_manifest import read_manifest


def digest(path: Path) -> str:
    h = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def inspect(manga: Path, chapter: str, page: str) -> dict:
    root = Path(manga).resolve()
    if (not isinstance(chapter, str) or not chapter or chapter in (".", "..")
            or Path(chapter).name != chapter or "\\" in chapter
            or not isinstance(page, str) or not page.lower().endswith(".png")
            or Path(page).name != page or "\\" in page):
        raise ValueError("Capítulo ou página inválido.")
    merge = next((p for p in _listing_merge_artifacts(images_root(root) / chapter)
                  if p.name == page), None)
    if merge is None or not merge.resolve().is_relative_to(root):
        raise ValueError("Página MERGE não comprovada pelo manifesto de origem.")
    final_file = final_manifest_path(root, chapter)
    if not final_file.is_file() or not final_file.resolve().is_relative_to(root):
        raise ValueError("Consolidado Final indisponível.")
    final = read_manifest(final_file, root, chapter)
    entry = final["pages"].get(page)
    current = final_file.parent.parent / page
    if (not isinstance(entry, dict) or entry.get("artifact") != page
            or not current.is_file() or not current.resolve().is_relative_to(root)
            or digest(current) != entry.get("sha256")):
        raise ValueError("Página atual sem integridade comprovada no Consolidado Final.")
    check = manifest_path(root, chapter)
    check_info = {"present": check.is_file(), "sha256": digest(check) if check.is_file() else None}
    return {
        "chapter": chapter, "page": page,
        "merge": {"sha256": digest(merge), "source": "MERGE", "bytes": merge.stat().st_size},
        "current": {"sha256": digest(current), "origin": entry.get("origin")},
        "final_manifest_sha256": digest(final_file),
        "check_manifest": check_info,
        "same_pixels_file": digest(merge) == digest(current),
        "can_apply": False,
        "blocked_reason": "Publicação e invalidação coordenadas ainda não implementadas.",
        "next_required": "Verificar snapshots, máscaras e consumidores downstream antes da escrita."
    }
