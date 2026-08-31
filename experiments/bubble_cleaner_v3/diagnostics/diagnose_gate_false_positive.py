#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np

def bbox_from(obj):
    for key in ("bbox", "box", "xyxy", "detection_box"):
        v = obj.get(key) if isinstance(obj, dict) else None
        if isinstance(v, (list, tuple)) and len(v) == 4:
            return tuple(int(round(float(x))) for x in v)
    return None

def collect_detection_like(obj: Any, path="$"):
    out = []
    if isinstance(obj, dict):
        did = obj.get("id", obj.get("detection_id"))
        bb = bbox_from(obj)
        if did is not None and bb is not None:
            out.append((path, obj, int(did), bb))
        for k, v in obj.items():
            out.extend(collect_detection_like(v, f"{path}.{k}"))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out.extend(collect_detection_like(v, f"{path}[{i}]"))
    return out

def find_ocr_terms(obj: Any, term: str, path="$"):
    out = []
    t = term.lower()
    if isinstance(obj, dict):
        text = obj.get("text")
        if isinstance(text, str) and t in text.lower():
            out.append((path, obj))
        for k, v in obj.items():
            out.extend(find_ocr_terms(v, term, f"{path}.{k}"))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out.extend(find_ocr_terms(v, term, f"{path}[{i}]"))
    return out

def resolve_source(report_path: Path, report: dict, sample_dir: Path):
    # Try explicit source fields first.
    for key in ("source", "source_image", "image", "input"):
        v = report.get(key)
        if isinstance(v, str):
            p = Path(v)
            if not p.is_absolute():
                p = (report_path.parent / p).resolve()
            if p.exists():
                return p

    # Infer from page folder and chapter path stored in sample-summary.
    page_name = report_path.parent.name
    summary = sample_dir / "sample-summary.json"
    if summary.exists():
        try:
            sd = json.loads(summary.read_text(encoding="utf-8"))
            chapter = Path(sd["chapter"])
            cand = chapter / f"{page_name}.png"
            if cand.exists():
                return cand
            for ext in (".jpg", ".jpeg", ".webp"):
                cand = chapter / f"{page_name}{ext}"
                if cand.exists():
                    return cand
        except Exception:
            pass
    return None

def region_metrics(img, bbox):
    h, w = img.shape[:2]
    x1, y1, x2, y2 = bbox
    x1, x2 = sorted((max(0, x1), min(w, x2)))
    y1, y2 = sorted((max(0, y1), min(h, y2)))
    if x2 <= x1 or y2 <= y1:
        return None

    crop = img[y1:y2, x1:x2]
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)

    # Generic ink/foreground occupancy indicators.
    dark_220 = float(np.mean(gray < 220))
    dark_200 = float(np.mean(gray < 200))
    dark_180 = float(np.mean(gray < 180))
    bright_245 = float(np.mean(gray >= 245))

    # Saturated/colorful pixels: colored SFX tends to be much higher than
    # black text inside white balloons.
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    saturated = float(np.mean(hsv[:, :, 1] >= 45))
    vivid = float(np.mean((hsv[:, :, 1] >= 70) & (hsv[:, :, 2] >= 120)))

    return {
        "bbox": [x1, y1, x2, y2],
        "width": x2 - x1,
        "height": y2 - y1,
        "area": int((x2-x1)*(y2-y1)),
        "dark_ratio_lt220": round(dark_220, 4),
        "dark_ratio_lt200": round(dark_200, 4),
        "dark_ratio_lt180": round(dark_180, 4),
        "bright_ratio_ge245": round(bright_245, 4),
        "saturated_ratio_ge45": round(saturated, 4),
        "vivid_ratio": round(vivid, 4),
    }

def main():
    ap = argparse.ArgumentParser(description="Diagnóstico read-only do gate visual V3.4.")
    ap.add_argument("sample_dir", nargs="?", type=Path,
                    default=Path("bubble_cleaner_output/v3-4-sample-28"))
    ap.add_argument("--term", default="STARE")
    args = ap.parse_args()

    sample_dir = args.sample_dir.resolve()
    reports = sorted(sample_dir.glob("page-*/report.json"))
    if not reports:
        raise SystemExit(f"[ERRO] Nenhum report.json encontrado em {sample_dir}")

    print("DIAGNÓSTICO READ-ONLY — GATE VISUAL / FALSO POSITIVO")
    print(f"Amostra: {sample_dir}")
    print(f"Termo alvo: {args.term}")
    print()

    output = {"diagnostic": "v3_4_gate_false_positive", "term": args.term, "pages": []}

    for rp in reports:
        report = json.loads(rp.read_text(encoding="utf-8"))
        hits = find_ocr_terms(report, args.term)
        if not hits:
            continue

        src = resolve_source(rp, report, sample_dir)
        if src is None:
            print(f"[AVISO] {rp.parent.name}: origem não localizada.")
            continue

        img = cv2.imread(str(src), cv2.IMREAD_COLOR)
        if img is None:
            print(f"[AVISO] {rp.parent.name}: falha ao ler {src}")
            continue

        dets = collect_detection_like(report)
        by_id = {}
        for path, obj, did, bb in dets:
            by_id.setdefault(did, []).append((path, obj, bb))

        page_out = {"page": rp.parent.name, "source": str(src), "ocr_hits": []}
        print(f"=== {rp.parent.name} ===")
        print(f"Origem: {src.name}")

        for opath, ocr in hits:
            did = ocr.get("detection_id")
            print(f"OCR: {ocr.get('text')!r} conf={ocr.get('confidence')} detection_id={did}")
            print(f"  decisão={ocr.get('decision')}")

            det_infos = []
            if did in by_id:
                for dpath, dobj, bb in by_id[did]:
                    met = region_metrics(img, bb)
                    if met:
                        entry = {
                            "json_path": dpath,
                            "confidence": dobj.get("confidence"),
                            "gate_approved": dobj.get("gate_approved", dobj.get("visual_gate_approved")),
                            "bbox": list(bb),
                            "metrics": met,
                        }
                        det_infos.append(entry)
                        print(f"  detecção: {dpath}")
                        print(f"    bbox={met['bbox']} tamanho={met['width']}x{met['height']}")
                        print(f"    dark<220={met['dark_ratio_lt220']:.4f}")
                        print(f"    bright>=245={met['bright_ratio_ge245']:.4f}")
                        print(f"    saturated>=45={met['saturated_ratio_ge45']:.4f}")
                        print(f"    vivid={met['vivid_ratio']:.4f}")
            else:
                print("  [AVISO] Não encontrei bbox estruturado para esse detection_id no report.")

            page_out["ocr_hits"].append({
                "ocr_path": opath,
                "ocr": ocr,
                "detections": det_infos,
            })

        output["pages"].append(page_out)
        print()

    out = sample_dir / "gate-false-positive-diagnostic.json"
    out.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] Relatório: {out}")
    print("[INFO] Nenhum arquivo do cleaner ou imagem foi alterado.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
