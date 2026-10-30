"""Public read-only page/chapter validation API for Combo Turbo."""
from pathlib import Path

from processamento.unificacao_imagens import image_stitcher as v3
from central_v2.backend.operational_log import emit
from central_v2.backend.state.work_layout import images_root
from central_v2.backend.orchestration.textoff_merged.solid_stage import rows_for
from central_v2.backend.orchestration.textoff_merged.stages import LEVEL1, stage_chapter
from central_v2.backend.orchestration.textoff_merged.artifact_paths import json_file

from .glass_validator import validate_glass_page
from .models import result, valid_chapter_id, valid_page_id
from .solids_validator import validate_solids_page


def validate_page(manga: Path, provider: str, chapter: str,
                  page: str, stage: str) -> dict:
    """Validate one existing artifact; never execute or write operational data."""
    key = str(stage).upper() if isinstance(stage, str) else ""
    emit("DEBUG", "validando artefato", component="COMBO",
         obra=str(manga), capítulo=chapter, página=page, etapa=key)
    if not valid_chapter_id(chapter):
        item = result(key or "UNKNOWN", chapter, page, "INVALID", reasons=["INVALID_CHAPTER"])
    elif key == "SOLIDOS":
        item = validate_solids_page(manga, provider, chapter, page)
    elif key == "GLASS":
        item = validate_glass_page(manga, provider, chapter, page)
    else:
        item = result(key or "UNKNOWN", chapter, page, "INVALID",
                      reasons=["UNKNOWN_STAGE"])
    emit("DEBUG", "resultado da validação", component="COMBO",
         capítulo=chapter, página=page, etapa=key,
         status=item["status"], motivos=",".join(item["reasons"]) or "—",
         integridade=item.get("integrity_ok"), check=item.get("check_verified"),
         artefato_sha256=item.get("artifact_sha256"),
         mascara_sha256=item.get("mask_sha256"),
         manifesto_sha256=item.get("manifest_sha256"))
    return item


def validate_chapter(manga: Path, provider: str, chapter: str) -> dict:
    """Return page-level statuses and aggregate counts for one chapter."""
    if not valid_chapter_id(chapter):
        empty = _counts([])
        return {"chapter": chapter, "pages_analyzed": 0, "solids": empty, "glass": dict(empty),
                "without_artifact": 0, "stale": 0, "invalid": 0, "unverified": 0,
                "pages": [], "results": {"SOLIDOS": [], "GLASS": []},
                "status": "INVALID", "reasons": ["INVALID_CHAPTER"]}
    root = Path(manga).resolve()
    pages = set()
    merge_dir = v3.merge_output_dir(images_root(root) / chapter)
    try:
        pages.update(path.name for path in v3.merge_artifact_files(merge_dir))
    except (OSError, ValueError, TypeError):
        pass
    try:
        import json
        level1 = stage_chapter(root, LEVEL1, chapter)
        manifest = json.loads(json_file(level1, "clean-manifest.json").read_text(encoding="utf-8"))
        pages.update(manifest.get("source_artifacts", []))
        pages.update(Path(name).name.replace("_clean", "")
                     for name in manifest.get("clean_artifacts", [])
                     if isinstance(name, str))
    except (OSError, ValueError, TypeError, RuntimeError):
        pass
    try:
        approved, _ = rows_for(root, {"provider": provider, "obra": root.name,
                                      "capitulo": chapter}, chapter)
        pages.update(row.get("page") for row in approved if valid_page_id(row.get("page")))
    except (OSError, ValueError, TypeError, KeyError):
        pass
    pages = sorted(page for page in pages if valid_page_id(page))
    records = {stage: [validate_page(root, provider, chapter, page, stage)
                       for page in pages] for stage in ("SOLIDOS", "GLASS")}
    counts = {stage.lower(): _counts(items) for stage, items in records.items()}
    summary = {
        "chapter": chapter, "pages_analyzed": len(pages),
        "solids": counts["solidos"], "glass": counts["glass"],
        "without_artifact": sum(1 for page in pages if all(
            rows[page]["status"] == "MISSING" for rows in _by_page(records).values())),
        "stale": sum(counts[stage]["STALE"] for stage in counts),
        "invalid": sum(counts[stage]["INVALID"] for stage in counts),
        "unverified": sum(counts[stage]["UNVERIFIED"] for stage in counts),
    }
    emit("DEBUG", "validação do capítulo concluída", component="COMBO", capítulo=chapter,
         páginas=summary["pages_analyzed"],
         solids={key.lower(): value for key, value in counts["solidos"].items()},
         glass={key.lower(): value for key, value in counts["glass"].items()})
    return {**summary, "pages": pages, "results": records}


def _counts(items):
    return {status: sum(item["status"] == status for item in items)
            for status in ("REUSABLE", "MISSING", "STALE", "INVALID", "UNVERIFIED")}


def _by_page(records):
    return {stage: {item["page"]: item for item in items}
            for stage, items in records.items()}
