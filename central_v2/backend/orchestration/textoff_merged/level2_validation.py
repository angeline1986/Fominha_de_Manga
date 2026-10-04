"""Selection, staged-report validation, and atomic promotion for Level II."""
import os
from pathlib import Path
import shutil
import uuid

from .artifact_paths import artifact_file, artifact_ref
from .execution import validate_selection
from .level2_vision import AUTHORIZED_DILATION, BASE_DILATION, LAMA_PADDING, REFERENCE_RECIPE
from .query import query_merged_level2
from .stages import LEVEL1


def validate_level2_selection(manga: Path, chapters: object) -> list[str]:
    selected = validate_selection(manga, chapters)
    rows = {row["chapter"]: row for row in query_merged_level2(manga)["chapters"]}
    for name in selected:
        row = rows.get(name)
        if not row or row["level2_status"] != "pending" or not row["selectable"]:
            raise ValueError(f"Capítulo {name} não possui balões transparentes pendentes do Nível I.")
    return selected


def promote_stage(staged: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    backup = target.parent / f".{target.name}.backup-level2-{uuid.uuid4().hex}"
    had_previous = target.exists()
    try:
        if had_previous:
            os.replace(target, backup)
        os.replace(staged, target)
    except Exception:
        if had_previous and backup.exists() and not target.exists():
            os.replace(backup, target)
        raise
    else:
        if backup.exists():
            shutil.rmtree(backup)


def validated_candidate_pages(report, candidate_names, staged, level1_dir):
    """Validate one analytical row per candidate, including no-change rows."""
    candidates = set(candidate_names)
    raw_pages = report.get("pages")
    if not isinstance(raw_pages, list) or not candidates:
        raise RuntimeError("Nível II não gerou resultados analíticos para as páginas candidatas.")
    by_source = {}
    for item in raw_pages:
        if not isinstance(item, dict):
            raise RuntimeError("Nível II gerou uma linha de resultado inválida.")
        source = item.get("source")
        if not isinstance(source, str) or source not in candidates or source in by_source:
            raise RuntimeError("Nível II gerou fontes ausentes, duplicadas ou inesperadas.")
        by_source[source] = item
    if set(by_source) != candidates:
        raise RuntimeError("Nível II não analisou todas as páginas candidatas.")

    validated = []
    for source in sorted(candidates):
        item = by_source[source]
        expected = artifact_ref("clean", Path(source).stem + "_clean" + Path(source).suffix)
        level1_clean = item.get("level1_clean")
        if level1_clean != expected or artifact_file(level1_dir, level1_clean, "clean") is None:
            raise RuntimeError(f"Nível II não referenciou o Nível I de {source}.")
        mask = item.get("mask")
        if not mask or artifact_file(staged, mask, "mask") is None:
            raise RuntimeError(f"Nível II não gerou máscara analítica válida para {source}.")
        changed, mask_pixels = item.get("changed_pixels"), item.get("mask_pixels")
        if not _nonnegative_integer(changed):
            raise RuntimeError(f"Nível II gerou contagem de alteração inválida para {source}.")
        if not _nonnegative_integer(mask_pixels):
            raise RuntimeError(f"Nível II gerou contagem de máscara inválida para {source}.")
        clean = item.get("clean")
        if clean is None:
            if changed != 0:
                raise RuntimeError(f"Nível II omitiu PNG alterado para {source}.")
        elif clean != expected or changed == 0 or artifact_file(staged, clean, "clean") is None:
            raise RuntimeError(f"Nível II referenciou PNG clean inválido para {source}.")
        if item.get("changed_outside_mask") != 0:
            raise RuntimeError(f"Nível II violou a máscara analítica em {source}.")
        validated.append({**item, "level1_clean": level1_clean})
    if report.get("pages_analyzed") != len(candidates):
        raise RuntimeError("Nível II informou uma contagem incompatível de páginas analisadas.")
    return validated


def build_output_manifest(report, pages, images, candidate_names, level1, level1_hash):
    clean_names = [item["clean"] for item in pages if item["clean"] is not None]
    changed = [item["source"] for item in pages if item["clean"] is not None]
    unchanged = [item["source"] for item in pages if item["clean"] is None]
    level1_clean = {item["source"]: item["level1_clean"] for item in pages}
    page_results = [{key: item.get(key, default) for key, default in (
        ("source", None), ("clean", None), ("level1_clean", None), ("mask", None),
        ("changed_pixels", 0), ("mask_pixels", 0), ("protected_occurrences", 0),
        ("protected_pixels", 0), ("mask_pixels_before_protection", 0),
        ("mask_pixels_after_protection", 0), ("protected_types", []),
        ("no_change_reason", None))} for item in pages]
    return {
        "schema_version": 1, "algorithm": report.get("algorithm"),
        "source_stage": LEVEL1, "integrity_ok": True,
        "source_artifacts": [path.name for path in images],
        "candidate_source_artifacts": sorted(candidate_names),
        "analyzed_source_artifacts": sorted(candidate_names),
        "changed_source_artifacts": sorted(changed), "unchanged_source_artifacts": sorted(unchanged),
        "page_results": page_results,
        "source_level1_artifacts": [item for item in level1.get("clean_artifacts", [])
                                    if Path(item).name.replace("_clean", "") in candidate_names],
        "source_level1_manifest_sha256": level1_hash,
        "clean_artifacts": clean_names, "outputs_total": len(clean_names),
        "pages_total": len(candidate_names), "analyzed_pages_total": len(pages),
        "changed_pages_total": len(changed), "changed_artifacts": clean_names,
        "mask_artifacts": [item["mask"] for item in pages],
        "level1_fallback_artifacts": [level1_clean[source] for source in unchanged],
        "recipe": {"reference": REFERENCE_RECIPE, "base_dilation": BASE_DILATION,
                   "authorized_dilation": AUTHORIZED_DILATION, "lama_padding": LAMA_PADDING},
        "pages_with_text": report.get("pages_with_text", 0),
        "mask_pixels": report.get("mask_pixels", 0),
        "protected_occurrences": report.get("protected_occurrences", 0),
        "protected_pixels": report.get("protected_pixels", 0),
        "mask_pixels_before_protection": report.get("mask_pixels_before_protection", 0),
        "mask_pixels_after_protection": report.get("mask_pixels_after_protection", 0),
        "protected_types": report.get("protected_types", []),
        "changed_pixels": report.get("changed_pixels", 0), "outcome": report.get("outcome"),
        "report": report.get("report_reference"),
        "execution": {"duration_seconds": report.get("duration_seconds"),
                      "duration_scope": "chapter_total_including_mask_creation_inpainting_and_validation"},
    }, clean_names


def _nonnegative_integer(value):
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0
