"""Independently validate a treatment result against the immutable input."""
from pathlib import Path

from .artifacts import contained_file, sha256


def verify(source: Path, result: Path, target: Path, metadata: dict) -> dict:
    import cv2
    import numpy as np

    reference = metadata["artifacts"].get("authorized_mask")
    reference = reference or metadata["artifacts"].get("authorized_mask_9x9")
    mask_path = contained_file(target, reference)
    result = contained_file(target, str(result.relative_to(target)))
    original = cv2.imread(str(source))
    output = cv2.imread(str(result))
    mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
    if original is None or output is None or mask is None:
        raise ValueError("Imagem ou máscara ilegível.")
    if original.shape != output.shape or mask.shape != original.shape[:2]:
        raise ValueError("Dimensões divergentes entre entrada, saída e máscara.")
    active = mask > 0
    if not np.any(active):
        raise ValueError("Máscara autorizada vazia.")
    changed = np.any(original != output, axis=2)
    outside = int(np.count_nonzero(changed & ~active))
    if outside:
        raise ValueError(f"Resultado inválido: {outside} pixels alterados fora da máscara.")
    return {"width": original.shape[1], "height": original.shape[0],
            "changed_pixels": int(np.count_nonzero(changed)),
            "mask_pixels": int(np.count_nonzero(active)), "changed_outside_mask": outside,
            "result_sha256": sha256(result), "mask_sha256": sha256(mask_path)}
