"""Per-work experiment storage with read access to earlier global runs."""
from pathlib import Path
import re

from .catalog import ROOT
from central_v2.backend.state.work_layout import secondary_root

NAMES = {"textoff_especiais_v2", "textoff_laboratorio"}
RUN_ID = re.compile(r"[A-Za-z0-9]{1,64}\Z")
LEGACY_SOLIDS_PREVIEWS = "_laboratorio_solidos_previews"


def legacy_root(name: str) -> Path:
    _check_name(name)
    return ROOT / "reports" / "experimentos" / name


def legacy_solids_root(output_root: Path) -> Path:
    return Path(output_root).resolve() / LEGACY_SOLIDS_PREVIEWS


def staging_root(manga: Path, name: str) -> Path:
    _check_name(name)
    work = Path(manga).resolve()
    root = (secondary_root(work) / "05_Lab_Retoques" / name).resolve()
    if not root.is_relative_to(work):
        raise ValueError("Área de retoques fora da obra.")
    return root


def run_folder(manga: Path, name: str, run_id: str, *, legacy: Path | None = None) -> Path:
    if not isinstance(run_id, str) or not RUN_ID.fullmatch(run_id):
        raise ValueError("Identidade da execução inválida.")
    root = staging_root(manga, name)
    current = (root / run_id).resolve()
    if not current.is_relative_to(root):
        raise ValueError("Execução fora da área de retoques.")
    if current.is_dir():
        return current
    return legacy_folder(legacy if legacy is not None else legacy_root(name), run_id)


def legacy_folder(root: Path, run_id: str) -> Path:
    if not isinstance(run_id, str) or not RUN_ID.fullmatch(run_id):
        raise ValueError("Identidade da execução inválida.")
    base = Path(root).resolve()
    folder = (base / run_id).resolve()
    if not folder.is_relative_to(base):
        raise ValueError("Execução fora da área legada.")
    return folder


def run_from_manifest(run: dict, name: str, *, legacy: Path | None = None) -> Path:
    source = run.get("source") or {}
    manga = source.get("manga")
    if not isinstance(manga, str) or not Path(manga).is_absolute():
        if legacy is not None and RUN_ID.fullmatch(str(run.get("run_id"))):
            return legacy_folder(legacy, run["run_id"])
        raise ValueError("Obra da execução inválida.")
    return run_folder(Path(manga), name, run.get("run_id"), legacy=legacy)


def roots(manga: Path, name: str, *, legacy: Path | None = None) -> tuple[Path, Path]:
    return staging_root(manga, name), (legacy if legacy is not None else legacy_root(name))


def _check_name(name: str) -> None:
    if name not in NAMES:
        raise ValueError("Tipo de experimento inválido.")
