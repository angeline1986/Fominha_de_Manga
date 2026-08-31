#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

def contains_term(obj: Any, term: str) -> bool:
    t = term.lower()
    if isinstance(obj, dict):
        return any(contains_term(k, term) or contains_term(v, term) for k, v in obj.items())
    if isinstance(obj, list):
        return any(contains_term(v, term) for v in obj)
    if isinstance(obj, str):
        return t in obj.lower()
    return False

def find_term_paths(obj: Any, term: str, path: str = "$"):
    found = []
    t = term.lower()
    if isinstance(obj, dict):
        for k, v in obj.items():
            kp = f"{path}.{k}"
            if isinstance(k, str) and t in k.lower():
                found.append((kp, k))
            found.extend(find_term_paths(v, term, kp))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            found.extend(find_term_paths(v, term, f"{path}[{i}]"))
    elif isinstance(obj, str) and t in obj.lower():
        found.append((path, obj))
    return found

def compact_context(obj: Any):
    if not isinstance(obj, dict):
        return obj
    interesting = {}
    for key in (
        "text", "ocr_text", "label", "confidence", "ocr_confidence",
        "box", "bbox", "polygon", "points", "center",
        "authorized", "decision", "reason", "status",
        "detector_id", "detection_id", "bubble_id", "associated_detection",
        "association", "overlap", "overlap_ratio", "inside_ratio",
        "gate_approved", "visual_gate_approved",
        "protected_box", "protected_bbox", "mask_pixels",
    ):
        if key in obj:
            interesting[key] = obj[key]
    return interesting or obj

def collect_parent_contexts(obj: Any, term: str, path: str = "$"):
    out = []
    t = term.lower()
    if isinstance(obj, dict):
        local_hit = any(
            isinstance(v, str) and t in v.lower()
            for v in obj.values()
        )
        if local_hit:
            out.append((path, compact_context(obj)))
        for k, v in obj.items():
            out.extend(collect_parent_contexts(v, term, f"{path}.{k}"))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out.extend(collect_parent_contexts(v, term, f"{path}[{i}]"))
    return out

def main():
    parser = argparse.ArgumentParser(
        description="Diagnóstico read-only da autorização indevida de texto solto (ex.: STARE)."
    )
    parser.add_argument(
        "sample_dir",
        nargs="?",
        type=Path,
        default=Path("bubble_cleaner_output/v3-4-sample-28"),
    )
    parser.add_argument("--term", default="STARE")
    args = parser.parse_args()

    sample_dir = args.sample_dir.resolve()
    if not sample_dir.exists():
        raise SystemExit(f"[ERRO] Diretório não encontrado: {sample_dir}")

    json_files = sorted(sample_dir.rglob("*.json"))
    matches = []

    for jf in json_files:
        try:
            data = json.loads(jf.read_text(encoding="utf-8"))
        except Exception:
            continue
        if contains_term(data, args.term):
            matches.append((jf, data))

    print("DIAGNÓSTICO READ-ONLY — ASSOCIAÇÃO DE TEXTO")
    print(f"Diretório: {sample_dir}")
    print(f"Termo: {args.term}")
    print(f"JSONs analisados: {len(json_files)}")
    print(f"Arquivos com ocorrência: {len(matches)}")
    print()

    if not matches:
        print("[INFO] O termo não aparece nos JSONs da amostra.")
        print("[INFO] Nesse caso, o próximo diagnóstico deve usar a máscara/overlay da página visualmente identificada.")
        return 2

    report = {
        "diagnostic": "bubble_cleaner_v3_4_authorization_trace",
        "term": args.term,
        "sample_dir": str(sample_dir),
        "matches": [],
    }

    for jf, data in matches:
        rel = jf.relative_to(sample_dir)
        print(f"=== {rel} ===")

        term_paths = find_term_paths(data, args.term)
        contexts = collect_parent_contexts(data, args.term)

        print("Ocorrências:")
        for p, value in term_paths:
            print(f"  {p}: {value!r}")

        print("Contextos estruturados:")
        if contexts:
            for p, ctx in contexts:
                print(f"  {p}")
                print(json.dumps(ctx, ensure_ascii=False, indent=4))
        else:
            print("  (nenhum contexto pai estruturado encontrado)")

        item = {
            "file": str(rel),
            "occurrences": [{"path": p, "value": v} for p, v in term_paths],
            "contexts": [{"path": p, "data": ctx} for p, ctx in contexts],
        }
        report["matches"].append(item)
        print()

    out = sample_dir / "stare-authorization-diagnostic.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] Relatório: {out}")
    print("[INFO] Nenhuma imagem, máscara ou algoritmo foi alterado.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
