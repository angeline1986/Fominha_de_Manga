"""Command-line entry point for TextOff Merged Level II."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

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
        print(f"Merged Nível II: {len(results) - len(failed)}/{len(results)} capítulo(s) processados.", flush=True)
        return 1 if failed else 0
    if not all((args.source_dir, args.level1_dir, args.output_dir, args.report)):
        parser.error("informe --batch-manifest ou todos os argumentos de capítulo")
    report = process(args.source_dir, args.level1_dir, args.output_dir, args.report, args.progress)
    print(f"Merged Nível II: {report['pages_with_text']}/{report['pages_analyzed']} página(s) com texto autorizado.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
