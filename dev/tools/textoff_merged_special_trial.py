"""Run Merged III–V previews from verified Level I chapter outputs."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from central_v2.backend.orchestration.textoff_merged.special_levels import execute_special_level
from central_v2.backend.orchestration.textoff_special.artifacts import write_json
from orquestracao.central_session import legacy_server_active


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manga", type=Path, required=True)
    parser.add_argument("--level", choices=("III", "IV", "V"), required=True)
    parser.add_argument("--chapters", nargs="+", required=True)
    parser.add_argument("--protected-strokes", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    protected = {}
    if args.protected_strokes:
        import json
        protected = json.loads(args.protected_strokes.read_text(encoding="utf-8"))
    def preflight():
        if legacy_server_active():
            raise RuntimeError("Central V1 ativa; TextOff V2 cancelado.")
    results = execute_special_level(args.manga, args.level, args.chapters,
        lambda chapter, event: print(f"{chapter}: {event['message']}", flush=True),
        protected_strokes=protected, preflight=preflight)
    report = {"schema_version": 1, "level": args.level,
              "manga": str(args.manga.resolve()), "chapters": args.chapters,
              "created_at": datetime.now(timezone.utc).isoformat(), "results": results,
              "official_files_modified": False, "promotion_allowed": False}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    write_json(args.report, report)
    print(f"Relatório: {args.report}")
    return 0 if all(item.get("status") == "ok" for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
