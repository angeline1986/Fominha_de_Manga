"""Durable, integrity-checked result state for an isolated Combo run."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import uuid

from central_v2.backend.orchestration.textoff_special.artifacts import sha256

SCHEMA = "combo_run_result_v1"
RESULT_FILE = "combo-run-result.json"


def new_run_id():
    return uuid.uuid4().hex


def new_run_result(run_id, provider, manga, chapters, root, signature):
    now = datetime.now(timezone.utc).isoformat()
    return {"schema": SCHEMA, "version": 1, "run_id": run_id,
            "provider": provider, "manga": Path(manga).name,
            "chapters": list(chapters), "workspace_root": str(Path(root).resolve()),
            "source_signature": signature, "status": "RUNNING",
            "created_at": now, "updated_at": now,
            "results": [{"chapter": chapter, "status": "PENDING", "pages": [],
                         "errors": []} for chapter in chapters], "errors": []}


def set_chapter_result(result, chapter_row):
    for index, row in enumerate(result["results"]):
        if row["chapter"] == chapter_row["chapter"]:
            result["results"][index] = chapter_row
            return
    result["results"].append(chapter_row)


def blocked_chapter(plan, reason):
    pages = []
    for row in plan.get("pages", []):
        reasons = list(row.get("stages", {}).get("SOLIDOS", {}).get("reasons", []))
        reasons += row.get("stages", {}).get("GLASS", {}).get("reasons", [])
        pages.append({"page": row["page"], "status": "BLOCKED",
            "eligible": dict(row.get("eligible", {})), "treatments": {},
            "artifact_id": None, "image_path": None, "report_path": None,
            "image_sha256": None, "report_sha256": None, "source_manifests": {},
            "check_sha256": None, "mask_sha256": None, "conflict_pixels": 0,
            "reasons": sorted(set(reasons + [reason])),
            "composition": {"status": "BLOCKED", "reasons": [reason]}})
    return {"chapter": plan.get("chapter"), "status": "BLOCKED", "pages": pages,
            "errors": [{"reason": reason, "detail": plan.get("error")}]}


def page_record(provider, manga, chapter, plan_page, outcome, run_root):
    composition = outcome.get("composition") or {}
    status = outcome.get("status", composition.get("status", "FAILED"))
    artifact = composition.get("result_path")
    report = composition.get("report_path")
    root = Path(run_root).resolve()
    stages = plan_page.get("stages", {})
    manga = Path(manga).resolve()
    source_refs = _manifest_references(manga, chapter)
    return {"provider": provider, "manga": manga.name,
        "chapter": chapter, "page": outcome["page"], "status": status,
        "eligible": dict(plan_page.get("eligible", {})),
        "treatments": {name: {"planned": row.get("needed", False),
            "reused": row.get("status") == "REUSED", "status": row.get("status")}
            for name, row in stages.items()},
        "artifact_id": str(Path(artifact).parent.relative_to(root)) if artifact else None,
        "image_path": artifact, "report_path": report,
        "image_sha256": composition.get("result_sha256"),
        "report_sha256": sha256(Path(report)) if report and Path(report).is_file() else None,
        "source_manifests": {key: composition.get(key) for key in (
            "check_manifest_sha256", "level1_manifest_sha256",
            "source_solids_sha256", "source_glass_sha256", "mask_sha256")},
        "source_manifest_refs": source_refs,
        "check_sha256": composition.get("check_manifest_sha256"),
        "mask_sha256": composition.get("mask_sha256"),
        "conflict_pixels": composition.get("overlap_pixels", 0),
        "reasons": list(dict.fromkeys(outcome.get("reasons", [])
                                      + composition.get("reasons", []))),
        "solids": outcome.get("solids"), "glass": outcome.get("glass"),
        "composition": composition}


def _manifest_references(manga, chapter):
    from central_v2.backend.orchestration.textoff_merged.auto_cleaner_check_manifest import manifest_path
    from central_v2.backend.orchestration.textoff_merged.stages import LEVEL1, LEVEL2, stage_chapter
    paths = {"check": manifest_path(manga, chapter),
        "level1": stage_chapter(manga, LEVEL1, chapter) / "json/clean-manifest.json",
        "glass": stage_chapter(manga, LEVEL2, chapter) / "json/clean-manifest.json",
        "solids": stage_chapter(manga, "05_AUTO_CLEANER_SOLIDOS", chapter,
                                  read_legacy=False) / "solid-white-manifest.json"}
    return {key: {"path": str(path.relative_to(manga)),
                  "sha256": sha256(path) if path.is_file() else None}
            for key, path in paths.items()}


def write_result(root, result):
    root = Path(root).resolve()
    result["updated_at"] = datetime.now(timezone.utc).isoformat()
    payload = json.dumps(result, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":")).encode("utf-8")
    envelope = {"sha256": hashlib.sha256(payload).hexdigest(),
                "result": json.loads(payload)}
    write_json_atomic(root / RESULT_FILE, envelope)


def write_json_atomic(target, value):
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
    with temporary.open("xb") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8"))
        stream.write(b"\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, target)
    descriptor = os.open(target.parent, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def read_result(root, *, run_id, provider, manga, chapters, signature):
    path = Path(root).resolve() / RESULT_FILE
    envelope = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(envelope, dict):
        raise ValueError("Envelope do resultado Combo inválido.")
    result = envelope.get("result")
    canonical = json.dumps(result, ensure_ascii=False, sort_keys=True,
                           separators=(",", ":")).encode("utf-8")
    if (not isinstance(result, dict)
            or hashlib.sha256(canonical).hexdigest() != envelope.get("sha256")
            or result.get("schema") != SCHEMA or result.get("version") != 1
            or result.get("run_id") != run_id or result.get("provider") != provider
            or result.get("manga") != Path(manga).name
            or result.get("chapters") != list(chapters)
            or result.get("source_signature") != signature
            or result.get("workspace_root") != str(Path(root).resolve())):
        raise ValueError("Resultado Combo persistido inválido ou incompatível.")
    rows = result.get("results")
    if (not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows)
            or [row.get("chapter") for row in rows] != list(chapters)
            or any(not isinstance(row.get("pages"), list) for row in rows)):
        raise ValueError("Capítulos do resultado Combo persistido estão incompletos.")
    allowed = {"COMPOSED", "NO_WORK", "CONFLICT", "BLOCKED", "FAILED", "INVALID"}
    for row in rows:
        pages = row["pages"]
        if (any(not isinstance(page, dict) for page in pages)
                or len({page.get("page") for page in pages}) != len(pages)
                or any(page.get("status") not in allowed for page in pages)):
            raise ValueError("Estados ou páginas duplicados no resultado Combo.")
    _verify_composed_artifacts(result, root)
    return result


def _verify_composed_artifacts(result, root):
    root = Path(root).resolve()
    for chapter in result.get("results", []):
        for page in chapter.get("pages", []):
            if page.get("status") != "COMPOSED":
                continue
            for field, expected in (("image_path", page.get("image_sha256")),
                                    ("report_path", page.get("report_sha256"))):
                raw = page.get(field)
                path = Path(raw).resolve() if isinstance(raw, str) else root
                if (not path.is_relative_to(root) or not path.is_file()
                        or not expected or sha256(path) != expected):
                    raise ValueError("Artefato Combo persistido ausente ou alterado.")
            composition = page.get("composition", {})
            if (composition.get("status") != "COMPOSED"
                    or composition.get("result_sha256") != page.get("image_sha256")
                    or composition.get("page") != page.get("page")):
                raise ValueError("Proveniência composta diverge do resultado persistido.")
