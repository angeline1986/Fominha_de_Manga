"""Run one preview from an explicit JSON request; no promotion operations."""
import argparse
import json
from pathlib import Path

from .artifacts import read_json
from .execution import preview


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manga", type=Path, required=True)
    parser.add_argument("--request", type=Path, required=True)
    args = parser.parse_args()
    result = preview(args.manga, read_json(args.request))
    print(json.dumps({key: result.get(key) for key in (
        "run_id", "execution_status", "duration_seconds", "validation", "error",
    )}, ensure_ascii=False, indent=2))
    return 0 if result["execution_status"] == "succeeded" else 1


if __name__ == "__main__":
    raise SystemExit(main())
