"""Explicit treatment identities and their dedicated runtimes."""
from dataclasses import dataclass
from pathlib import Path
import os

ROOT = Path(__file__).resolve().parents[4]
RUNTIME_ROOT = ROOT / "central_v2/runtime/textoff/especiais"
STAGING_ROOT = ROOT / "reports/experimentos/textoff_especiais_v2"


@dataclass(frozen=True)
class Treatment:
    key: str
    runtime: str
    algorithm: str
    module: str
    function: str


TREATMENTS = {
    "degrade": Treatment(
        "degrade", "patch_degrade", "textoff_special_roi_degrade_v2",
        "textoff_special_roi", "run_degrade_roi",
    ),
    "estilizado": Treatment(
        "estilizado", "patch_estilizado", "textoff_special_roi_styled_v1",
        "textoff_special_styled_roi", "run_styled_roi",
    ),
    "gradiente_suave": Treatment(
        "gradiente_suave", "degrade_suave", "textoff_gradiente_suave_v1",
        "gradiente_suave.gradiente_suave", "reconstruct_many",
    ),
    "transparente": Treatment(
        "transparente", "balao_transparente", "textoff_special_roi_transparent_v1",
        "textoff_special_transparent_roi", "run_transparent_roi",
    ),
    "transparente_legacy": Treatment(
        "transparente_legacy", "balao_transparente_legado",
        "textoff_special_roi_transparent_legacy_v1",
        "textoff_special_transparent_legacy_roi", "run_transparent_legacy_roi",
    ),
}


def treatment_for(key: str) -> Treatment:
    if not isinstance(key, str) or key not in TREATMENTS:
        raise ValueError("Tratamento especial inválido.")
    return TREATMENTS[key]


def runtime_folder(key: str) -> Path:
    return RUNTIME_ROOT / treatment_for(key).runtime


def python_for(key: str) -> Path:
    binary = "Scripts/python.exe" if os.name == "nt" else "bin/python"
    interpreter = runtime_folder(key) / ".venv" / binary
    if not interpreter.is_file():
        raise RuntimeError(f"Ambiente de Casos Especiais ausente: {interpreter}")
    return interpreter
