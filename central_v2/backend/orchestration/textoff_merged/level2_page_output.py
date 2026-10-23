"""Resolve page inputs and compose the Level II output without widening its mask."""
from pathlib import Path

import numpy as np
from PIL import Image

from central_v2.backend.orchestration.textoff_special.artifacts import sha256
from .level2_provenance import capture_sources, verify_sources
from .level2_reset_base import load_reset_base


def load_page_inputs(source, level1_path, reset_bases):
    """Load the original, Level I image, and optional page-scoped reset base."""
    consumed = capture_sources(source, level1_path)
    with Image.open(source) as image:
        original = np.asarray(image.convert("RGB"))
    with Image.open(level1_path) as image:
        level1 = np.asarray(image.convert("RGB"))
    verify_sources({"source": source, "level1": level1_path}, consumed)
    reset_path, reset_digest, reset_source = load_reset_base(source.name, reset_bases)
    if reset_path is None:
        return original, level1, level1, None, None, consumed
    with Image.open(reset_path) as image:
        base = np.asarray(image.convert("RGB"))
    if base.shape != level1.shape:
        raise ValueError(f"Dimensões inválidas na imagem Reset de {source.name}.")
    return original, level1, base, reset_source, (reset_path, reset_digest), consumed


def compose_output(level1, base, final, mask):
    """Apply Glass pixels over the selected base and measure output integrity."""
    result = base.copy()
    active = mask > 0
    result[active] = final[active]
    outside = int(np.count_nonzero(np.any(result != base, axis=2) & ~active))
    changed = int(np.count_nonzero(np.any(result != level1, axis=2)))
    return result, outside, changed


def verify_reset_input(reset_input):
    """Recheck a Reset file after image processing and before its report is saved."""
    if reset_input and sha256(Path(reset_input[0])) != reset_input[1]:
        raise ValueError("Imagem de Reset mudou durante a execução do Nível II.")
