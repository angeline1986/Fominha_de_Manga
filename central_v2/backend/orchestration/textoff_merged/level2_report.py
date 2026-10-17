"""Build the Level II execution report without changing its processing policy."""
import time

from .level2_vision import (
    ALGORITHM, AUTHORIZED_DILATION, BASE_DILATION, LAMA_PADDING, REFERENCE_RECIPE,
)
from .stages import LEVEL1


def build_report(started, model, model_path, device, analyzed, total, pages,
                 protection_totals, protected_types, level1_manifest_hash):
    changed = sum(page["changed_pixels"] for page in pages)
    masks = sum(page["mask_pixels"] for page in pages)
    return {
        "schema_version": 1, "algorithm": ALGORITHM,
        "mask_sources": ["Level I deferred Cleaner V2 components inside the matching transparent balloon"],
        "base_dilation": [BASE_DILATION, BASE_DILATION],
        "authorized_dilation": [AUTHORIZED_DILATION, AUTHORIZED_DILATION],
        "lama_padding": LAMA_PADDING, "reference_recipe": REFERENCE_RECIPE,
        "source_stage": LEVEL1, "source_level1_manifest_sha256": level1_manifest_hash,
        "text_detector": "Cleaner V2 deferred text mask", "text_recognition": False,
        "inpainter": "anime-manga-big-lama" if model else None,
        "model_path": model_path, "device": device,
        "pages_analyzed": analyzed, "merge_pages_total": total,
        "duration_seconds": round(time.perf_counter() - started, 3),
        "pages_with_text": sum(page["mask_pixels"] > 0 for page in pages),
        "mask_pixels": masks, **protection_totals,
        "protected_types": sorted(protected_types),
        "fully_protected_pages": sum(page["no_change_reason"] is not None for page in pages),
        "protection_pixel_semantics": "protected_pixels counts automatic mask pixels removed by manual protection",
        "changed_pixels": changed,
        "outcome": "visual_changes" if changed else "no_visual_change",
        "integrity_ok": all(page["changed_outside_mask"] == 0 for page in pages),
        "pages": pages,
    }
