"""Execute the explicitly authorized A/B matrix and retain every run outcome."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from central_v2.backend.orchestration.textoff_special.artifacts import read_json, sha256, write_json
from central_v2.backend.orchestration.textoff_special.catalog import STAGING_ROOT
from central_v2.backend.orchestration.textoff_special.execution import preview


def execute(inventory_path: Path, report_path: Path) -> dict:
    inventory = read_json(inventory_path)
    if inventory.get("roi_status") != "fixed_for_comparison":
        raise ValueError("Fixe e registre as ROIs antes de iniciar a matriz.")
    report = {"schema_version": 1, "inventory_sha256": sha256(inventory_path),
              "created_at": datetime.now(timezone.utc).isoformat(), "runs": []}
    if report_path.exists():
        report = read_json(report_path)
        if report["inventory_sha256"] != sha256(inventory_path):
            raise ValueError("O inventário mudou; use outro arquivo de relatório.")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    complete = {(r["chapter"], r["level"], r["filename"], r["treatment"]) for r in report["runs"]}
    for source in inventory["inputs"]:
        for key in ("transparente", "transparente_legacy"):
            identity = (source["chapter"], source["level"], source["filename"], key)
            if identity in complete:
                continue
            payload = {"treatment": key, "level": source["level"], "chapter": source["chapter"],
                       "filename": source["filename"], "expected_sha256": source["sha256"],
                       "selections": source["selections"]}
            print(f"Iniciando {identity}", flush=True)
            result = preview(Path(inventory["local_work_root"]), payload)
            entry = {**payload, "run_id": result["run_id"],
                     "manifest": str((STAGING_ROOT / result["run_id"] / "manifest.json").relative_to(ROOT)),
                     "execution_status": result["execution_status"],
                     "duration_seconds": result["duration_seconds"],
                     "validation": result.get("validation"), "error": result.get("error")}
            report["runs"].append(entry)
            write_json(report_path, report)
            print(f"{result['execution_status']}: {result['run_id']}", flush=True)
    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    report["inputs_unchanged"] = all(
        sha256(Path(inventory["local_work_root"]) / source["path_relative_to_work"]) == source["sha256"]
        for source in inventory["inputs"]
    )
    write_json(report_path, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    report = execute(args.inventory, args.report)
    print(f"Matriz registrada: {len(report['runs'])} execuções; entradas intactas: {report['inputs_unchanged']}")
    return 0 if report["inputs_unchanged"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
