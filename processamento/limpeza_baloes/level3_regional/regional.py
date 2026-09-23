"""Correção Assistida — processamento regional independente.

Implementação isolada do restante do Texto Off.

Não modifica Cleaner V2.
Não modifica Tratamentos Especiais.
Não modifica imagens oficiais durante geração de preview.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import cv2
import easyocr
import numpy as np
import torch
from PIL import Image
from simple_lama_inpainting import SimpleLama


ALGORITHM = "textoff_level3_regional_v1"

OCR_LANGUAGES = ["en"]

BRIGHT_THRESHOLD = 175
LOCAL_CONTRAST_THRESHOLD = 10

OCR_REGION_KERNEL = (5, 5)
LOCAL_BLUR_KERNEL = (11, 11)
CLOSE_KERNEL = (3, 3)

V2_DILATION_KERNEL = (5, 5)
V3_DILATION_KERNEL = (5, 5)

CONTEXT_PADDING = 120


def _bbox(value: str) -> tuple[int, int, int, int]:
    try:
        values = tuple(int(v) for v in value.split(","))
    except ValueError:
        raise argparse.ArgumentTypeError(
            "BBox deve conter quatro inteiros."
        ) from None

    if len(values) != 4:
        raise argparse.ArgumentTypeError(
            "BBox deve conter x1,y1,x2,y2."
        )

    return values


def _validate_bbox(
    bbox: tuple[int, int, int, int],
    width: int,
    height: int,
) -> tuple[int, int, int, int]:

    x1, y1, x2, y2 = bbox

    if not (
        0 <= x1 < x2 <= width
        and 0 <= y1 < y2 <= height
    ):
        raise ValueError(
            f"BBox inválida {bbox} para {width}x{height}."
        )

    return bbox


def _detect_mask(
    crop_bgr: np.ndarray,
    reader: easyocr.Reader,
) -> tuple[np.ndarray, list[dict]]:

    gray = cv2.cvtColor(
        crop_bgr,
        cv2.COLOR_BGR2GRAY,
    )

    detections_raw = reader.readtext(
        crop_bgr,
        detail=1,
        paragraph=False,
    )

    mask = np.zeros(
        gray.shape,
        dtype=np.uint8,
    )

    detections: list[dict] = []

    # Igual ao POC V2 validado:
    # contraste é calculado sobre o crop inteiro.
    blur = cv2.GaussianBlur(
        gray,
        LOCAL_BLUR_KERNEL,
        0,
    )

    local_contrast = cv2.subtract(
        gray,
        blur,
    )

    for box, text, confidence in detections_raw:

        pts = np.asarray(
            [
                [
                    int(round(point[0])),
                    int(round(point[1])),
                ]
                for point in box
            ],
            dtype=np.int32,
        )

        region = np.zeros_like(mask)

        cv2.fillPoly(
            region,
            [pts],
            255,
        )

        region = cv2.dilate(
            region,
            cv2.getStructuringElement(
                cv2.MORPH_ELLIPSE,
                OCR_REGION_KERNEL,
            ),
            iterations=1,
        )

        candidate = (
            (gray >= BRIGHT_THRESHOLD)
            & (
                local_contrast
                >= LOCAL_CONTRAST_THRESHOLD
            )
            & (region > 0)
        ).astype(np.uint8) * 255

        mask = cv2.bitwise_or(
            mask,
            candidate,
        )

        detections.append(
            {
                "text": str(text),
                "confidence": float(confidence),
                "polygon": pts.tolist(),
            }
        )

    # V2 aprovada.
    mask = cv2.morphologyEx(
        mask,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE,
            CLOSE_KERNEL,
        ),
    )

    mask = cv2.dilate(
        mask,
        cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE,
            V2_DILATION_KERNEL,
        ),
        iterations=1,
    )

    # V3 aprovada:
    # refinamento mínimo de mais uma dilatação 5x5.
    mask = cv2.dilate(
        mask,
        cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE,
            V3_DILATION_KERNEL,
        ),
        iterations=1,
    )

    return mask, detections


def generate(
    source_path: Path,
    clean_path: Path,
    output_path: Path,
    report_path: Path,
    bboxes: list[tuple[int, int, int, int]],
    model_path: Path,
) -> dict:

    source_bgr = cv2.imread(
        str(source_path),
        cv2.IMREAD_COLOR,
    )

    clean_bgr = cv2.imread(
        str(clean_path),
        cv2.IMREAD_COLOR,
    )

    if source_bgr is None:
        raise RuntimeError(
            f"Source não encontrada: {source_path}"
        )

    if clean_bgr is None:
        raise RuntimeError(
            f"Clean não encontrada: {clean_path}"
        )

    if source_bgr.shape != clean_bgr.shape:
        raise RuntimeError(
            "Dimensões SOURCE/CLEAN divergentes."
        )

    height, width = source_bgr.shape[:2]

    if not bboxes:
        raise ValueError(
            "Nenhuma região selecionada."
        )

    reader = easyocr.Reader(
        OCR_LANGUAGES,
        gpu=False,
    )

    full_mask = np.zeros(
        (height, width),
        dtype=np.uint8,
    )

    regions = []

    for index, bbox in enumerate(bboxes, 1):

        x1, y1, x2, y2 = _validate_bbox(
            bbox,
            width,
            height,
        )

        crop = source_bgr[
            y1:y2,
            x1:x2,
        ].copy()

        local_mask, detections = _detect_mask(
            crop,
            reader,
        )

        destination = full_mask[
            y1:y2,
            x1:x2,
        ]

        np.maximum(
            destination,
            local_mask,
            out=destination,
        )

        regions.append(
            {
                "index": index,
                "bbox_pixels": [
                    x1, y1, x2, y2
                ],
                "mask_pixels": int(
                    np.count_nonzero(
                        local_mask
                    )
                ),
                "detections": detections,
            }
        )

    ys, xs = np.where(
        full_mask > 0
    )

    if len(xs) == 0:
        raise RuntimeError(
            "Máscara regional vazia."
        )

    wx1 = max(
        0,
        int(xs.min()) - CONTEXT_PADDING,
    )

    wy1 = max(
        0,
        int(ys.min()) - CONTEXT_PADDING,
    )

    wx2 = min(
        width,
        int(xs.max()) + 1 + CONTEXT_PADDING,
    )

    wy2 = min(
        height,
        int(ys.max()) + 1 + CONTEXT_PADDING,
    )

    source_rgb = cv2.cvtColor(
        source_bgr,
        cv2.COLOR_BGR2RGB,
    )

    clean_rgb = cv2.cvtColor(
        clean_bgr,
        cv2.COLOR_BGR2RGB,
    )

    source_crop_np = source_rgb[
        wy1:wy2,
        wx1:wx2,
    ]

    mask_crop_np = full_mask[
        wy1:wy2,
        wx1:wx2,
    ]

    os.environ["LAMA_MODEL"] = str(
        model_path
    )

    device = (
        torch.device("mps")
        if torch.backends.mps.is_available()
        else torch.device("cpu")
    )

    lama = SimpleLama(
        device=device
    )

    lama_np = np.asarray(
        lama(
            Image.fromarray(
                source_crop_np
            ),
            Image.fromarray(
                mask_crop_np,
                mode="L",
            ),
        )
    )

    expected_h, expected_w = (
        mask_crop_np.shape
    )

    if (
        lama_np.shape[0] < expected_h
        or lama_np.shape[1] < expected_w
    ):
        raise RuntimeError(
            "LaMa retornou imagem menor "
            "que o crop solicitado."
        )

    # Mesmo comportamento comprovado no POC:
    # normaliza eventual alinhamento maior do LaMa.
    lama_np = lama_np[
        :expected_h,
        :expected_w,
    ]

    result_rgb = clean_rgb.copy()

    target = result_rgb[
        wy1:wy2,
        wx1:wx2,
    ]

    before = target.copy()

    authorized = (
        mask_crop_np > 0
    )

    target[authorized] = (
        lama_np[authorized]
    )

    # Prova explícita de segurança.
    changed = np.any(
        target != before,
        axis=2,
    )

    outside_changed = int(
        np.count_nonzero(
            changed & (~authorized)
        )
    )

    if outside_changed != 0:
        raise RuntimeError(
            "SEGURANÇA: alteração detectada "
            "fora da máscara autorizada."
        )

    result_rgb[
        wy1:wy2,
        wx1:wx2,
    ] = target

    result_bgr = cv2.cvtColor(
        result_rgb,
        cv2.COLOR_RGB2BGR,
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if not cv2.imwrite(
        str(output_path),
        result_bgr,
    ):
        raise RuntimeError(
            "Falha ao salvar preview."
        )

    report = {
        "algorithm": ALGORITHM,
        "device": str(device),
        "model": str(model_path),
        "context_padding": CONTEXT_PADDING,
        "selection_count": len(bboxes),
        "mask_pixels": int(
            np.count_nonzero(full_mask)
        ),
        "outside_mask_changed_pixels":
            outside_changed,
        "work_bbox_pixels": [
            wx1, wy1, wx2, wy2
        ],
        "regions": regions,
    }

    report_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    report_path.write_text(
        json.dumps(
            report,
            indent=2,
            ensure_ascii=False,
        ) + "\n",
        encoding="utf-8",
    )

    return report


def main() -> int:

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--source",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--clean",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--output",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--report",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--model",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--bbox",
        type=_bbox,
        action="append",
        required=True,
    )

    args = parser.parse_args()

    report = generate(
        args.source,
        args.clean,
        args.output,
        args.report,
        args.bbox,
        args.model,
    )

    print(
        json.dumps(
            report,
            indent=2,
            ensure_ascii=False,
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
