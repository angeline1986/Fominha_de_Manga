#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path
import cv2
import numpy as np
from PIL import Image

def read_rgb(path: Path) -> np.ndarray:
    with Image.open(path) as im:
        return np.asarray(im.convert("RGB"))

def read_gray(path: Path) -> np.ndarray:
    with Image.open(path) as im:
        return np.asarray(im.convert("L"))

def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnóstico V3.2 — máscara vs resíduo")
    parser.add_argument("source", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()

    source = args.source.resolve()
    output_dir = args.output_dir.resolve()
    mask_path = output_dir / "authorized-mask.png"
    cleaned_path = output_dir / "cleaned-preview.png"
    report_path = output_dir / "report.json"

    for p in (source, mask_path, cleaned_path, report_path):
        if not p.exists():
            raise SystemExit(f"[ERRO] Arquivo não encontrado: {p}")

    src = read_rgb(source)
    cleaned = read_rgb(cleaned_path)
    mask = read_gray(mask_path)
    report = json.loads(report_path.read_text(encoding="utf-8"))

    approved = [d for d in report.get("detections", []) if d.get("gate_ok")]
    if not approved:
        raise SystemExit("[ERRO] Nenhuma detecção aprovada no report.json.")

    d = approved[0]
    x1, y1, x2, y2 = map(int, [d["x1"], d["y1"], d["x2"], d["y2"]])

    src_gray = cv2.cvtColor(src, cv2.COLOR_RGB2GRAY)
    cleaned_gray = cv2.cvtColor(cleaned, cv2.COLOR_RGB2GRAY)
    roi_clean = cleaned_gray[y1:y2, x1:x2]
    roi_mask = mask[y1:y2, x1:x2]

    margin = max(6, int(round(min(x2-x1, y2-y1) * 0.04)))
    inner = np.zeros_like(roi_clean, dtype=np.uint8)
    if roi_clean.shape[0] > 2*margin and roi_clean.shape[1] > 2*margin:
        inner[margin:-margin, margin:-margin] = 1

    residual = (roi_clean <= 90) & (inner > 0)
    inside = residual & (roi_mask > 0)
    outside = residual & ~(roi_mask > 0)

    n, labels, stats, _ = cv2.connectedComponentsWithStats(
        residual.astype(np.uint8), connectivity=8
    )
    comps = []
    for label in range(1, n):
        x, y, w, h, area = stats[label].tolist()
        comp = labels == label
        inside_count = int(np.count_nonzero(comp & (roi_mask > 0)))
        outside_count = int(np.count_nonzero(comp & ~(roi_mask > 0)))
        comps.append({
            "x": int(x+x1), "y": int(y+y1), "w": int(w), "h": int(h), "area": int(area),
            "inside_mask_pixels": inside_count,
            "outside_mask_pixels": outside_count,
            "classification": "inside_mask" if outside_count == 0 else "outside_mask" if inside_count == 0 else "mixed",
        })

    likely = [c for c in comps if c["area"] <= 500 and c["w"] <= 60 and c["h"] <= 40]
    likely.sort(key=lambda c: (c["area"], c["y"], c["x"]))

    result = {
        "source": str(source),
        "output_dir": str(output_dir),
        "summary": {
            "residual_dark_pixels_inside_detector": int(np.count_nonzero(residual)),
            "residual_dark_pixels_inside_authorized_mask": int(np.count_nonzero(inside)),
            "residual_dark_pixels_outside_authorized_mask": int(np.count_nonzero(outside)),
            "small_components": len(likely),
        },
        "likely_residual_components": likely[:30],
    }
    out_json = output_dir / "mask-diagnostic.json"
    out_json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print("DIAGNÓSTICO V3.2 — MÁSCARA VS RESÍDUO")
    print()
    s = result["summary"]
    print(f"Pixels escuros residuais no balão: {s['residual_dark_pixels_inside_detector']}")
    print(f"  dentro da máscara autorizada: {s['residual_dark_pixels_inside_authorized_mask']}")
    print(f"  fora da máscara autorizada:   {s['residual_dark_pixels_outside_authorized_mask']}")
    print()
    print(f"Componentes pequenos candidatos: {len(likely)}")
    for i, c in enumerate(likely[:10], start=1):
        print(f"{i:02d}. x={c['x']} y={c['y']} w={c['w']} h={c['h']} area={c['area']} -> {c['classification']}")
    print()
    print(f"Relatório: {out_json}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
