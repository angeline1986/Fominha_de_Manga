"""Resolve image requests for new per-work runs and legacy global runs."""
from pathlib import Path

from central_v2.backend.orchestration.textoff_special.run_paths import legacy_folder, run_folder
from central_v2.backend.state.catalog import build_catalog
from central_v2.backend.state.manga_state import resolve_manga


def folder_for_request(payload: dict, output_root: Path, name: str,
                       legacy: Path) -> tuple[Path, Path | None]:
    def value(key):
        item = payload.get(key)
        return item[0] if isinstance(item, list) and item else item

    run_id = value("run_id")
    provider, manga_name = value("provider"), value("manga")
    if bool(provider) != bool(manga_name):
        raise ValueError("Obra da execução inválida.")
    if provider:
        if manga_name not in build_catalog(output_root).get(provider, []):
            raise ValueError("Obra da execução inválida.")
        manga = resolve_manga(output_root, provider, manga_name)
        return run_folder(manga, name, run_id, legacy=legacy), manga.resolve()
    return legacy_folder(legacy, run_id), None


def belongs_to_manga(record: dict, manga: Path | None) -> bool:
    return manga is None or (record.get("source") or {}).get("manga") == str(manga)
