"""Reconhecimento de transparência por reuso seguro dos artefatos do Nível I."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image

from .transparent_candidates import extract_candidates

ALGORITHM = "transparent_recognition_from_level1_v1"
LEVEL1_ALGORITHM = "textoff_level1_balloon_transparency_gate_v4"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def recognize(level1_dir: Path) -> dict:
    """Produz relatório em memória sem executar inferência ou alterar artefatos."""
    root = Path(level1_dir).resolve()
    manifest_file = root / "json/clean-manifest.json"
    report_file = root / "json/level1-balloon-report.json"

    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    report = json.loads(report_file.read_text(encoding="utf-8"))

    if manifest.get("integrity_ok") is not True:
        raise ValueError("Manifesto do Nível I não está íntegro.")
    if manifest.get("level1", {}).get("algorithm") != LEVEL1_ALGORITHM:
        raise ValueError("Algoritmo do Nível I incompatível.")
    if manifest.get("level1", {}).get("report") not in (
        "json/level1-balloon-report.json",
        "level1-balloon-report.json",
    ):
        raise ValueError("Relatório não corresponde ao manifesto do Nível I.")

    candidates = extract_candidates(report)
    pages = {item["source"]: item for item in report["pages"]}
    grouped = {}

    for item in candidates:
        grouped.setdefault(item["source"], []).append(item)

    mask_hashes = {}

    for source, items in grouped.items():
        reference = pages[source].get("transparent_mask_artifact")
        if not isinstance(reference, str):
            raise ValueError(f"Máscara ausente no relatório: {source}")

        mask_path = (root / reference).resolve()
        if not mask_path.is_relative_to(root) or not mask_path.is_file():
            raise ValueError(f"Máscara inválida: {source}")

        with Image.open(mask_path) as image:
            width, height = image.size
            if image.mode not in ("I;16", "I", "L"):
                raise ValueError(f"Formato de máscara inválido: {source}")

            for item in items:
                x, y, w, h = item["bbox"]
                if x + w > width or y + h > height:
                    raise ValueError(f"Geometria fora da máscara: {source}")

                import numpy as np

                pixels = np.asarray(
                    image.crop((x, y, x + w, y + h))
                )
                if not np.any(pixels == item["mask_label"]):
                    raise ValueError(f"Rótulo sem pixels na região: {source}")

        mask_hashes[source] = _sha256(mask_path)

    return {
        "schema": ALGORITHM,
        "source_algorithm": LEVEL1_ALGORITHM,
        "source_manifest_sha256": _sha256(manifest_file),
        "source_report_sha256": _sha256(report_file),
        "source_masks_sha256": mask_hashes,
        "pages_with_candidates": len(grouped),
        "candidate_count": len(candidates),
        "candidates": candidates,
    }
