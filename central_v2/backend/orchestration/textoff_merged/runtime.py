"""Resolve feature-specific Python environments for TextOff Merged workers."""
from __future__ import annotations

import os
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
TEXT_OFF_RUNTIME_ROOT = REPOSITORY_ROOT / "central_v2" / "runtime" / "textoff"


def python_for(feature: str) -> Path:
    """Return the interpreter for a V2 TextOff feature or fail with its path."""
    if not feature or Path(feature).name != feature:
        raise ValueError("Nome de runtime TextOff inválido.")
    binary = "Scripts/python.exe" if os.name == "nt" else "bin/python"
    interpreter = TEXT_OFF_RUNTIME_ROOT / feature / ".venv" / binary
    if not interpreter.is_file():
        raise RuntimeError(f"Ambiente da Central V2 não encontrado: {interpreter}")
    return interpreter
