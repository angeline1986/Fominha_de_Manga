"""Manual residue types with authority to protect pixels from Level II."""
import math

import cv2
import numpy as np

from .auto_cleaner_check_manifest import _read_check_manifest, manifest_path
from .occurrence_policy import protected_types_for_transparency_basic
from .residue_occurrences import MANIFEST_NAME, occurrences_for, read_manifest
from .stages import stage_chapter

LEVEL1_REVIEW_STEP = "1"
PROTECTED_FROM_LEVEL2 = protected_types_for_transparency_basic()


def protected_occurrences_by_page(manifest: dict) -> dict[str, list[dict]]:
    """Return only Level I review occurrences that declare regional protection."""
    result = {}
    pages = manifest.get("pages")
    if not isinstance(pages, dict):
        raise ValueError("Páginas inválidas no catálogo de resíduos.")
    for page, record in pages.items():
        if not isinstance(page, str) or not isinstance(record, dict):
            raise ValueError("Página inválida no catálogo de resíduos.")
        steps = record.get("steps", {})
        if not isinstance(steps, dict):
            raise ValueError("Revisões inválidas no catálogo de resíduos.")
        step_record = steps.get(LEVEL1_REVIEW_STEP)
        if step_record is None:
            continue
        if not isinstance(step_record, dict) or not isinstance(step_record.get("ocorrencias", []), list):
            raise ValueError("Ocorrências inválidas no catálogo do Passo 1.")
        occurrences = occurrences_for(manifest, page, LEVEL1_REVIEW_STEP)
        if not all(isinstance(item, dict) for item in occurrences):
            raise ValueError("Ocorrência inválida no catálogo do Passo 1.")
        protected = [item for item in occurrences if item.get("tipo") in PROTECTED_FROM_LEVEL2]
        if protected:
            result[page] = protected
    return result


def load_level1_protection(manga, provider: str, manga_name: str,
                           chapter: str) -> dict[str, list[dict]]:
    """Use saved Check decisions, or the legacy catalog if Check is absent."""
    document = {"provider": provider, "obra": manga_name, "capitulo": chapter}
    check_path = manifest_path(manga, chapter)
    if check_path.is_file():
        approved = _read_check_manifest(check_path, document)["approved_occurrences"]
        result = {}
        for item in approved:
            if item.get("tipo") not in PROTECTED_FROM_LEVEL2:
                continue
            page = item.get("page")
            if not isinstance(page, str) or not page or not isinstance(item.get("box_normalized"), dict):
                raise ValueError("Ocorrência protegida inválida no manifesto do Check.")
            result.setdefault(page, []).append(item)
        return result
    path = stage_chapter(manga, "RESIDUE_OCCURRENCES", chapter,
                         read_legacy=False) / MANIFEST_NAME
    manifest = read_manifest(path, document)
    return protected_occurrences_by_page(manifest)


def protection_mask(shape: tuple[int, int], occurrences: list[dict]) -> np.ndarray:
    """Rasterize normalized catalog boxes onto the exact image dimensions."""
    height, width = shape
    if height <= 0 or width <= 0:
        raise ValueError("Dimensões inválidas para a proteção manual do Nível II.")
    mask = np.zeros((height, width), dtype=np.uint8)
    for item in occurrences:
        if item.get("tipo") not in PROTECTED_FROM_LEVEL2:
            continue
        box = item.get("box_normalized")
        if not isinstance(box, dict):
            raise ValueError("Caixa normalizada inválida na proteção manual do Nível II.")
        left, top, box_width, box_height = (_coordinate(box, key) for key in
                                             ("left", "top", "width", "height"))
        if (left < 0 or top < 0 or box_width <= 0 or box_height <= 0
                or left + box_width > 1 or top + box_height > 1):
            raise ValueError("Caixa normalizada fora da imagem na proteção manual do Nível II.")
        x0 = max(0, min(width, math.floor(left * width)))
        y0 = max(0, min(height, math.floor(top * height)))
        x1 = max(0, min(width, math.ceil((left + box_width) * width)))
        y1 = max(0, min(height, math.ceil((top + box_height) * height)))
        mask[y0:y1, x0:x1] = 255
    return mask


def subtract_protection(mask: np.ndarray, protected: np.ndarray) -> np.ndarray:
    """Subtract manual pixels after all automatic mask expansion is complete."""
    if mask.shape != protected.shape:
        raise ValueError("Dimensões incompatíveis entre máscaras do Nível II.")
    return cv2.bitwise_and(mask, cv2.bitwise_not(protected))


def protect_level2_masks(balloon_masks: list[np.ndarray], occurrences: list[dict],
                        shape: tuple[int, int]) -> tuple[list[np.ndarray], dict]:
    """Apply protection after the per-balloon Level II masks have been dilated."""
    automatic = _union_masks(balloon_masks, shape)
    before = int(np.count_nonzero(automatic))
    protected_items = [item for item in occurrences if isinstance(item, dict)
                       and item.get("tipo") in PROTECTED_FROM_LEVEL2]
    types = sorted({item["tipo"] for item in protected_items})
    protection = protection_mask(shape, protected_items) if types else np.zeros(shape, dtype=np.uint8)
    protected_masks = ([subtract_protection(mask, protection) for mask in balloon_masks]
                       if types else balloon_masks)
    effective = _union_masks(protected_masks, shape)
    after = int(np.count_nonzero(effective))
    summary = {
        "protected_occurrences": len(protected_items),
        "protected_pixels": before - after,
        "mask_pixels_before_protection": before,
        "mask_pixels_after_protection": after,
        "protected_types": types,
        "no_change_reason": ("manual_protection_removed_all_level2_mask"
                             if before > 0 and after == 0 else None),
    }
    return protected_masks, summary


def _union_masks(masks: list[np.ndarray], shape: tuple[int, int]) -> np.ndarray:
    combined = np.zeros(shape, dtype=np.uint8)
    for mask in masks:
        cv2.bitwise_or(combined, mask, dst=combined)
    return combined


def progress_detail(analyzed: int, total: int, page: str, summary: dict) -> str:
    if summary["protected_pixels"]:
        return (f"Proteção manual aplicada · página={page} "
                f"ocorrências={summary['protected_occurrences']} pixels={summary['protected_pixels']}")
    return f"Reconstruindo texto autorizado ({analyzed}/{total})"


def _coordinate(box: dict, key: str) -> float:
    value = box.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("Coordenada inválida na proteção manual do Nível II.")
    return float(value)
