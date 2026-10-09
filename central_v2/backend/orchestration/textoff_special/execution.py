"""Create a traceable preview without modifying any official image or manifest."""
from datetime import datetime, timezone
from pathlib import Path
import shutil
import time
import uuid

from .artifacts import contained_file, read_json, sha256, write_json
from .catalog import STAGING_ROOT, python_for, treatment_for
from .inputs import assert_unchanged, resolve_input, validate_selections
from .process import run_worker


def preview(manga: Path, payload: dict, *, staging: Path = STAGING_ROOT,
            approved_check_rois: bool = False, on_progress=None,
            resolved_source: dict | None = None) -> dict:
    key = payload.get("treatment")
    treatment_for(key)
    python_for(key)
    selections = validate_selections(payload.get("selections"))
    source = (resolve_input(manga, payload.get("level"), payload.get("chapter"),
                            payload.get("filename"), payload.get("expected_sha256"))
              if resolved_source is None else _validate_resolved_source(
                  manga, payload, resolved_source))
    mask_sources = {}
    staging = staging.resolve()
    if staging.is_relative_to(manga.resolve()):
        raise ValueError("Staging deve ficar fora da obra.")
    run_id = uuid.uuid4().hex
    folder = staging / run_id
    (folder / "input").mkdir(parents=True)
    (folder / "logs").mkdir()
    request = {"schema_version": 1, "run_id": run_id, "treatment": key,
               "source": source, "selections": selections}
    if approved_check_rois:
        if key != "degrade":
            raise ValueError("Aprovação do Check só se aplica ao Degradê.")
        request["approved_check_rois"] = True
    if payload.get("merged_level") in {"IV", "V"}:
        request["merged_level"] = payload["merged_level"]
    mask_inputs = (("authorization_mask_path", "authorization_mask.png", "authorization_mask"),
                   ("preauthorized_mask_path", "preauthorized_mask.png", "preauthorized_mask"))
    for field, name, request_key in mask_inputs:
        raw_path = payload.get(field)
        if raw_path is None:
            continue
        mask_path = Path(raw_path).resolve()
        if (not mask_path.is_relative_to(manga.resolve())
                and not mask_path.is_relative_to(STAGING_ROOT.resolve())) or not mask_path.is_file():
            raise ValueError("Máscara fora das áreas de teste ou ausente.")
        mask_hash = sha256(mask_path)
        copied_mask = folder / "input" / name
        shutil.copyfile(mask_path, copied_mask)
        if sha256(copied_mask) != mask_hash:
            raise ValueError("PROPOSTA_OBSOLETA: máscara mudou durante o snapshot.")
        request[request_key] = f"input/{name}"
        mask_sources[name] = (mask_path, mask_hash)
    request["input_artifacts"] = {name: digest for name, (_, digest) in mask_sources.items()}
    manifest = {**request, "created_at": datetime.now(timezone.utc).isoformat(),
                "execution_status": "running", "visual_review_status": "pending",
                "promotion_allowed": False, "official_files_modified": False}
    write_json(folder / "manifest.json", manifest)
    started = time.monotonic()
    try:
        snapshot = folder / "input/source.png"
        shutil.copyfile(source["path"], snapshot)
        if sha256(snapshot) != source["sha256"]:
            raise ValueError("PROPOSTA_OBSOLETA: a entrada mudou durante o snapshot.")
        assert_unchanged(source)
        _assert_masks_unchanged(mask_sources)
        write_json(folder / "request.json", request)
        worker_args = (key, folder / "request.json", folder / "logs/worker.log")
        if on_progress is None:
            run_worker(*worker_args)
        else:
            run_worker(*worker_args, on_progress=on_progress)
        result = read_json(folder / "worker-result.json")
        output = contained_file(folder, result["result_file"])
        if sha256(output) != result["validation"]["result_sha256"]:
            raise ValueError("Resultado divergente da validação do worker.")
        assert_unchanged(source)
        _assert_masks_unchanged(mask_sources)
        manifest.update(result, execution_status="succeeded")
    except BaseException as exc:
        error_file = folder / "worker-error.json"
        detail = read_json(error_file) if error_file.is_file() else {"error": str(exc)}
        manifest.update(execution_status="failed", error=detail)
        if not isinstance(exc, Exception):
            raise
    finally:
        for name, filename in (("runtime", "runtime.json"), ("timings", "worker-timings.json")):
            if (folder / filename).is_file():
                manifest[name] = read_json(folder / filename)
        manifest["duration_seconds"] = round(time.monotonic() - started, 3)
        manifest["finished_at"] = datetime.now(timezone.utc).isoformat()
        write_json(folder / "manifest.json", manifest)
    return manifest


def _assert_masks_unchanged(sources: dict) -> None:
    for path, expected in sources.values():
        if sha256(path) != expected:
            raise ValueError("PROPOSTA_OBSOLETA: uma máscara de entrada mudou durante a execução.")


def _validate_resolved_source(manga, payload, source):
    path = Path(source.get("path", "")).resolve()
    if (not path.is_relative_to(Path(manga).resolve()) or not path.is_file()
            or source.get("sha256") != payload.get("expected_sha256")
            or source.get("level") != payload.get("level")
            or source.get("chapter") != payload.get("chapter")
            or source.get("filename") != payload.get("filename")
            or source.get("manga") != str(Path(manga).resolve())):
        raise ValueError("Snapshot Artístico não pertence ao contexto autorizado.")
    if sha256(path) != source["sha256"]:
        raise ValueError("Snapshot Artístico ausente ou com hash divergente.")
    assert_unchanged(source)
    return source
