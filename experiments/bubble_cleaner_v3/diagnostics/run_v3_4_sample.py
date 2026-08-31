#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}

def load_cleaner(root: Path):
    module_path = root / "experiments" / "bubble_cleaner_v3" / "bubble_cleaner_v3.py"
    spec = importlib.util.spec_from_file_location("bubble_cleaner_v3_runtime", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Não foi possível carregar {module_path}")

    mod = importlib.util.module_from_spec(spec)

    # Python 3.12 dataclasses expects the module to already exist in sys.modules
    # while decorators are executed during exec_module().
    sys.modules[spec.name] = mod
    try:
        spec.loader.exec_module(mod)
    except Exception:
        sys.modules.pop(spec.name, None)
        raise

    return mod

def evenly_spaced(items, count):
    if count >= len(items):
        return items[:]
    if count <= 1:
        return [items[0]]

    idxs = []
    for i in range(count):
        idx = round(i * (len(items) - 1) / (count - 1))
        if idx not in idxs:
            idxs.append(idx)
    return [items[i] for i in idxs]

def main():
    parser = argparse.ArgumentParser(description="Amostra visual Bubble Cleaner V3.4")
    parser.add_argument("chapter_dir", type=Path)
    parser.add_argument("--count", type=int, default=12)
    parser.add_argument("--output", type=Path, default=Path("bubble_cleaner_output/v3-4-sample"))
    args = parser.parse_args()

    root = Path.cwd().resolve()
    if not (root / "menu.py").exists():
        raise SystemExit("[ERRO] Execute na raiz de Fominha_de_Manga.")

    chapter_dir = args.chapter_dir.resolve()
    if not chapter_dir.exists():
        raise SystemExit(f"[ERRO] Capítulo não encontrado: {chapter_dir}")

    pages = sorted(
        p for p in chapter_dir.iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_EXTS
    )
    if not pages:
        raise SystemExit(f"[ERRO] Nenhuma imagem encontrada em {chapter_dir}")

    cleaner_path = root / "experiments" / "bubble_cleaner_v3" / "bubble_cleaner_v3.py"
    source_text = cleaner_path.read_text(encoding="utf-8")
    supported = (
        "Bubble Cleaner Experimental V3.4" in source_text
        or "Bubble Cleaner Experimental V3.5" in source_text
    )
    if not supported:
        raise SystemExit("[ERRO] A versão instalada não corresponde à V3.4/V3.5 esperada.")

    chosen = evenly_spaced(pages, min(max(args.count, 1), len(pages)))
    cleaner = load_cleaner(root)
    model_path = cleaner.resolve_model(None)
    languages = ["en"]

    print("AMOSTRA V3.4/V3.5 — VALIDAÇÃO EM PÁGINAS VARIADAS")
    print(f"Capítulo: {chapter_dir}")
    print(f"Páginas encontradas: {len(pages)}")
    print(f"Amostra selecionada: {len(chosen)}")
    print("Selecionadas:")
    for p in chosen:
        print(f"  - {p.name}")
    print()

    summaries = []
    failures = 0

    for p in chosen:
        try:
            payload = cleaner.process_image(
                p,
                args.output,
                model_path,
                languages,
                0.55,
            )
            s = payload["summary"]
            fill = payload.get("fill", {})
            summaries.append({
                "page": p.name,
                "integrity_ok": s["integrity_ok"],
                "detections": s["specialized_detections"],
                "gate_approved": s["visual_gate_approved"],
                "ocr_regions": s["ocr_regions"],
                "auto_clean": s["auto_clean"],
                "preserved": s["preserved"],
                "authorized_pixels": s["authorized_pixels"],
                "changed_outside_authorized_mask": s["changed_outside_authorized_mask"],
                "fill_strategy": fill.get("strategy"),
            })

            status = "OK" if s["integrity_ok"] else "BLOQUEADO"
            print(
                f"[{status}] {p.name}: "
                f"det={s['specialized_detections']} "
                f"gate={s['visual_gate_approved']} "
                f"ocr={s['ocr_regions']} "
                f"auto={s['auto_clean']} "
                f"preservado={s['preserved']} "
                f"fill={fill.get('strategy')} "
                f"fora={s['changed_outside_authorized_mask']}"
            )
        except Exception as exc:
            failures += 1
            print(f"[ERRO] {p.name}: {exc}")

    report = {
        "experiment": "bubble_cleaner_v3_4_sample_validation",
        "chapter": str(chapter_dir),
        "source_page_count": len(pages),
        "sample_count": len(chosen),
        "selected_pages": [p.name for p in chosen],
        "results": summaries,
        "failures": failures,
    }

    args.output.mkdir(parents=True, exist_ok=True)
    report_path = args.output / "sample-summary.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print()
    print(f"Resumo: {report_path.resolve()}")
    print(f"Previews: {args.output.resolve()}")
    return 1 if failures else 0

if __name__ == "__main__":
    raise SystemExit(main())
