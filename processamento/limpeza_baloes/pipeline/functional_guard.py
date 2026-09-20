"""Functional fail-closed guard for colored/gradient/textured balloons.

This is the first visible integration step of the refactored Texto Off pipeline.
Panel Cleaner may run in the isolated work directory, but before any legacy
authorization/post-processing is allowed to promote pixels, risky balloon
regions are restored from the immutable source and removed from the mask.

The guard is intentionally conservative. It does not clean Level V; it protects
those balloons so Level III cannot mutate them.
"""
from __future__ import annotations
from pathlib import Path
from typing import Any
import json

from .balloon_evidence import (
    MODEL_REPO, MODEL_FILE, MODEL_REVISION, CONF, IOU,
)

ALGORITHM = "textoff_level2_colored_balloon_guard_v1"

# Conservative safety gate, not final semantic classifier.
SAT_MEAN_RISK = 25.0
SAT_P90_RISK = 55.0
MIN_INTERIOR_PIXELS = 500

def protect_colored_balloons(source_images, output_dir: Path, report_path: Path) -> dict[str, Any]:
    try:
        import cv2
        import numpy as np
        from huggingface_hub import hf_hub_download
        from ultralytics import YOLO
    except ImportError as exc:
        raise RuntimeError("Colored Balloon Guard requer cv2, numpy, huggingface_hub e ultralytics.") from exc

    try:
        model_path = hf_hub_download(
            repo_id=MODEL_REPO, filename=MODEL_FILE, revision=MODEL_REVISION
        )
        model = YOLO(model_path)
    except Exception as exc:
        raise RuntimeError("Colored Balloon Guard não conseguiu carregar o segmentador.") from exc

    output_dir = Path(output_dir)
    pages = []
    protected_total = 0

    for src in map(Path, source_images):
        original = cv2.imread(str(src))
        if original is None:
            raise RuntimeError(f"Guard falhou ao ler original: {src}")

        cleans = sorted(p for p in output_dir.glob(f"{src.stem}_clean.*") if p.is_file())
        masks = sorted(p for p in output_dir.glob(f"{src.stem}_mask.*") if p.is_file())
        if len(cleans) != 1 or len(masks) != 1:
            raise RuntimeError(f"Guard esperava 1 clean e 1 mask para {src.name}.")
        clean_path, mask_path = cleans[0], masks[0]
        cleaned = cv2.imread(str(clean_path))
        cleaner_mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
        if cleaned is None or cleaner_mask is None:
            raise RuntimeError(f"Guard falhou ao ler artefatos de {src.name}.")
        if cleaned.shape != original.shape or cleaner_mask.shape[:2] != original.shape[:2]:
            raise RuntimeError(f"Guard encontrou dimensões divergentes em {src.name}.")

        result = model.predict(source=original, conf=CONF, iou=IOU, verbose=False)[0]
        hsv = cv2.cvtColor(original, cv2.COLOR_BGR2HSV)
        page_balloons = []

        if result.masks is not None:
            for idx, poly in enumerate(result.masks.xy, start=1):
                pts = np.asarray(poly, dtype=np.int32)
                if len(pts) < 3:
                    continue
                balloon = np.zeros(original.shape[:2], dtype=np.uint8)
                cv2.fillPoly(balloon, [pts], 255)

                # Erode to reduce black outline / neighboring scene contamination.
                area = int(np.count_nonzero(balloon))
                if area <= 0:
                    continue
                kernel = np.ones((9, 9), np.uint8)
                interior = cv2.erode(balloon, kernel, iterations=1)
                valid = interior > 0
                interior_pixels = int(np.count_nonzero(valid))
                if interior_pixels < MIN_INTERIOR_PIXELS:
                    valid = balloon > 0
                    interior_pixels = area

                sat = hsv[:, :, 1][valid].astype(np.float32)
                sat_mean = float(sat.mean()) if sat.size else 0.0
                sat_p90 = float(np.percentile(sat, 90)) if sat.size else 0.0

                # Two independent risk paths:
                # A) sustained chroma across the balloon interior;
                # B) strong chromatic tail combined with strong luminance variation.
                # B captures pale/gradient decorative balloons whose mean saturation
                # is diluted by near-white areas, without turning SAT90 alone into
                # a universal "colored balloon" rule.
                lum = cv2.cvtColor(original, cv2.COLOR_BGR2GRAY)[valid].astype(np.float32)
                lum_std = float(lum.std()) if lum.size else 0.0
                sustained_chroma = bool(
                    sat.size and
                    sat_mean >= SAT_MEAN_RISK and
                    sat_p90 >= SAT_P90_RISK
                )
                pale_gradient_risk = bool(
                    sat.size and
                    sat_p90 >= 80.0 and
                    lum_std >= 35.0
                )
                risky = sustained_chroma or pale_gradient_risk

                mask_pixels_before = int(np.count_nonzero(cleaner_mask[balloon > 0]))
                if risky:
                    # Whole balloon is protected: restore source and revoke mask.
                    cleaned[balloon > 0] = original[balloon > 0]
                    cleaner_mask[balloon > 0] = 0
                    protected_total += 1

                page_balloons.append({
                    "balloon_id": idx,
                    "area_pixels": area,
                    "interior_pixels": interior_pixels,
                    "saturation_mean": round(sat_mean, 4),
                    "saturation_p90": round(sat_p90, 4),
                    "luminance_std": round(lum_std, 4),
                    "risk_signals": {
                        "sustained_chroma": sustained_chroma,
                        "pale_gradient_risk": pale_gradient_risk,
                    },
                    "mask_pixels_before_guard": mask_pixels_before,
                    "protected_from_level3": risky,
                    "route_hint": "LEVEL_5" if risky else "UNDECIDED",
                })

        clean_tmp = clean_path.with_name(clean_path.stem + ".guard-tmp" + clean_path.suffix)
        mask_tmp = mask_path.with_name(mask_path.stem + ".guard-tmp" + mask_path.suffix)
        if not cv2.imwrite(str(clean_tmp), cleaned) or not cv2.imwrite(str(mask_tmp), cleaner_mask):
            clean_tmp.unlink(missing_ok=True); mask_tmp.unlink(missing_ok=True)
            raise RuntimeError(f"Guard falhou ao gravar artefatos de {src.name}.")
        clean_tmp.replace(clean_path); mask_tmp.replace(mask_path)

        pages.append({"source": src.name, "balloons": page_balloons})

    report = {
        "schema_version": 1,
        "algorithm": ALGORITHM,
        "mode": "FUNCTIONAL_FAIL_CLOSED_GUARD",
        "policy": "protect_colored_balloon_before_legacy_level3_authorization",
        "thresholds": {
            "saturation_mean_min": SAT_MEAN_RISK,
            "saturation_p90_min": SAT_P90_RISK,
            "pale_gradient_saturation_p90_min": 80.0,
            "pale_gradient_luminance_std_min": 35.0,
        },
        "protected_balloons_total": protected_total,
        "route": "LEVEL_5",
        "pixel_policy": "restore_original_and_zero_cleaner_mask_inside_protected_balloon",
        "pages": pages,
    }
    Path(report_path).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report
