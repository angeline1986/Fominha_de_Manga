"""Command-line entry point for TextOff Merged Level II."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from central_v2.backend.operational_log import emit
from .level2_batch import process_batch
from .level2_process import process

def main() -> int:
    parser = argparse.ArgumentParser(description="Texto Off Merged Nível II: texto em balões transparentes")
    parser.add_argument("--source-dir", type=Path)
    parser.add_argument("--level1-dir", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--progress", type=Path)
    parser.add_argument("--batch-manifest", type=Path,
                        help="JSON com vários capítulos; inicializa modelos uma única vez")
    args = parser.parse_args()
    if args.batch_manifest:
        jobs = json.loads(args.batch_manifest.read_text(encoding="utf-8"))
        results = process_batch(jobs, args.progress)
        failed = [item for item in results if item["report"].get("integrity_ok") is not True]
        emit("INFO", "processamento em lote concluído", component="MERGE-II",
             capítulos=f"{len(results) - len(failed)}/{len(results)}")
        return 1 if failed else 0
    if not all((args.source_dir, args.level1_dir, args.output_dir, args.report)):
        parser.error("informe --batch-manifest ou todos os argumentos de capítulo")
    report = process(args.source_dir, args.level1_dir, args.output_dir, args.report, args.progress)
    emit("INFO", "processamento do capítulo concluído", component="MERGE-II",
         páginas_com_texto=report["pages_with_text"], páginas_analisadas=report["pages_analyzed"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
