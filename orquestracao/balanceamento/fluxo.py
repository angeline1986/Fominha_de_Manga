"""V2 application boundary for the existing Balanceamento domain."""
from pathlib import Path
from typing import Callable

Progress = Callable[[str], None]


def read_state(manga: Path) -> dict:
    from processamento.balanceamento.consulta_v2 import read_balance_state
    return read_balance_state(manga)


def validate_state(manga: Path, progress: Progress | None = None) -> dict:
    from processamento.balanceamento.balanceamento import balance_state
    if progress:
        progress("Calculando e registrando a validação dos merges oficiais.")
    return balance_state(manga)


def prepare_manual(manga: Path, chapter: str, files: list[str], progress: Progress | None = None) -> dict:
    from processamento.balanceamento.balanceador import prepare_manual_balance
    callback = _domain_progress(chapter, progress)
    return prepare_manual_balance(manga, chapter, files, progress_callback=callback)


def generate_manual(manga: Path, chapter: str, files: list[str], cuts: list[int], progress: Progress | None = None) -> dict:
    from processamento.balanceamento.balanceador import generate_manual_balance
    callback = _domain_progress(chapter, progress)
    return generate_manual_balance(manga, chapter, files, cuts, progress_callback=callback)


def apply_manual(manga: Path, chapter: str, progress: Progress | None = None) -> dict:
    from processamento.balanceamento.balanceador import effect_manual_balance
    callback = _domain_progress(chapter, progress)
    return effect_manual_balance(manga, chapter, progress_callback=callback)


def _domain_progress(chapter: str, progress: Progress | None):
    if progress is None:
        return None
    return lambda step, total, detail: progress(f"Cap. {chapter}: {detail} ({step}/{total}).")
