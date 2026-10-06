"""Dedicated process entry point; imports image dependencies only in its own venv."""
import argparse
from pathlib import Path
import time
import traceback

from .artifacts import read_json, sha256, write_json
from .catalog import treatment_for
from .domain import run_pre_authorized_treatment, run_treatment
from .process import install_worker_cleanup
from .provenance import collect, model_records
from .verification import verify


def run(request: dict, folder: Path) -> dict:
    key = request["treatment"]
    definition = treatment_for(key)
    provenance = collect(key)
    write_json(folder / "runtime.json", provenance)
    source = folder / "input/source.png"
    if sha256(source) != request["source"]["sha256"]:
        raise ValueError("Snapshot divergente da entrada autorizada.")
    target = folder / "treatment"
    started = time.monotonic()
    if request.get("preauthorized_mask"):
        mask = (folder / request["preauthorized_mask"]).resolve()
        if not mask.is_relative_to(folder.resolve()) or not mask.is_file():
            raise ValueError("Máscara Nível I ausente ou inválida.")
        result, treatment, timings = run_pre_authorized_treatment(
            key, request["merged_level"], source, target, mask)
    else:
        result, treatment, timings = run_treatment(
            key, source, target, request["selections"],
            approved_check_rois=request.get("approved_check_rois") is True)
    expected_algorithm = (
        f"textoff_merged_level{request['merged_level']}_from_level1_mask_v1"
        if request.get("preauthorized_mask") else
        definition.algorithm)
    if treatment.get("algorithm") != expected_algorithm:
        raise ValueError("Algoritmo retornado não corresponde ao tratamento.")
    validation = verify(source, result, target, treatment)
    if sha256(source) != request["source"]["sha256"]:
        raise ValueError("O tratamento alterou o snapshot de entrada.")
    files = {str(p.relative_to(folder)): sha256(p) for p in target.rglob("*") if p.is_file()}
    return {"result_file": str(result.relative_to(folder)), "treatment": treatment,
            "validation": validation, "timings": timings,
            "worker_seconds": round(time.monotonic() - started, 3),
            "runtime": provenance, "models": model_records(treatment), "artifacts": files}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    args = parser.parse_args()
    folder = args.request.resolve().parent
    install_worker_cleanup()
    try:
        result = run(read_json(args.request), folder)
        write_json(folder / "worker-result.json", result)
        return 0
    except Exception as exc:
        write_json(folder / "worker-error.json", {"type": type(exc).__name__, "error": str(exc)})
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
