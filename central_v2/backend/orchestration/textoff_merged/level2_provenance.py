"""Capture and recheck files consumed by a Level II run."""
from pathlib import Path
import json
import string

from central_v2.backend.orchestration.textoff_special.artifacts import sha256
from .artifact_paths import artifact_file


def validate_report_provenance(pages, level1_hash, report_level1_hash, chapter=None):
    label = f"Cap. {chapter} " if chapter is not None else ""
    if not _is_sha256(level1_hash) or report_level1_hash != level1_hash:
        raise ValueError(f"{label}campo source_level1_manifest_sha256: hash ausente ou divergente.")
    for page in pages:
        source = page.get("source", "desconhecida")
        for field in ("source_sha256", "level1_sha256", "result_sha256", "mask_sha256"):
            if not _is_sha256(page.get(field)):
                _invalid(chapter, source, field, "hash ausente ou inválido")
        for field in ("level1_report_sha256", "level1_mask_sha256"):
            if not _is_sha256(page.get(field)):
                _invalid(chapter, source, field, "hash ausente ou inválido")
        if (page.get("deferred_mask_sha256") is not None
                and not _is_sha256(page["deferred_mask_sha256"])):
            _invalid(chapter, source, "deferred_mask_sha256", "hash inválido")
        source = page.get("protection_source")
        if (not isinstance(source, dict)
                or source.get("kind") not in {"CHECK", "RESIDUE_OCCURRENCES"}
                or not isinstance(source.get("path"), str)
                or Path(source["path"]).is_absolute() or ".." in Path(source["path"]).parts
                or (source.get("kind") == "CHECK" and not _is_sha256(source.get("sha256")))
                or (source.get("sha256") is not None and not _is_sha256(source["sha256"]))):
            _invalid(chapter, page.get("source", "desconhecida"), "protection_source",
                     "fonte inválida")
        ids, types = page.get("protected_occurrence_ids"), page.get("protected_types_applied")
        if (not isinstance(ids, list) or not isinstance(types, list)
                or page.get("protected_occurrences") != len(ids)
                or page.get("protected_types") != types):
            _invalid(chapter, page.get("source", "desconhecida"),
                     "protected_occurrence_ids/protected_types", "metadados ausentes ou incoerentes")


def validate_protection_provenance(report, pages, authority, protected_by_page, chapter):
    expected_source = dict(authority)
    totals = {key: 0 for key in ("protected_occurrences", "protected_pixels",
                                  "mask_pixels_before_protection", "mask_pixels_after_protection")}
    all_types = set()
    for page in pages:
        name = page["source"]
        expected = protected_by_page.get(name, [])
        if any(not isinstance(item.get("id"), str) or not item.get("id")
               for item in expected):
            _invalid(chapter, name, "authority.id", "ID de proteção ausente ou inválido")
        if any(not isinstance(item.get("tipo"), str) or not item.get("tipo")
               for item in expected):
            _invalid(chapter, name, "authority.tipo", "tipo de proteção ausente ou inválido")
        ids = sorted(item["id"] for item in expected)
        types = sorted({item["tipo"] for item in expected})
        for field, value in (("protection_source", expected_source),
                             ("protected_occurrence_ids", ids),
                             ("protected_types_applied", types),
                             ("protected_types", types),
                             ("protected_occurrences", len(ids))):
            if page.get(field) != value:
                _invalid(chapter, name, field, "diverge da autoridade capturada nesta execução")
        all_types.update(types)
        for field in ("protected_occurrences", "protected_pixels",
                      "mask_pixels_before_protection", "mask_pixels_after_protection"):
            value = page.get(field)
            if not _nonnegative_integer(value):
                _invalid(chapter, name, field, "contagem ausente ou inválida")
            totals[field] += value
        before, after = page["mask_pixels_before_protection"], page["mask_pixels_after_protection"]
        if after + page["protected_pixels"] != before:
            _invalid(chapter, name, "protected_pixels", "contagens de pixels não fecham")
        if after != page.get("mask_pixels"):
            _invalid(chapter, name, "mask_pixels_after_protection", "diverge de mask_pixels")
    for field, value in totals.items():
        if report.get(field) != value:
            _invalid(chapter, "relatório", field, "total diverge da soma das páginas")
    if report.get("protected_types") != sorted(all_types):
        _invalid(chapter, "relatório", "protected_types", "tipos divergem das páginas")


def _invalid(chapter, page, field, reason):
    prefix = f"Cap. {chapter} " if chapter is not None else ""
    raise ValueError(f"{prefix}página {page} campo {field}: {reason}.")


def _nonnegative_integer(value):
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _is_sha256(value):
    return (isinstance(value, str) and len(value) == 64
            and all(character in string.hexdigits for character in value))


def capture_sources(source, level1):
    return {"source": sha256(source), "level1": sha256(level1)}


def verify_sources(paths, hashes):
    if any(sha256(paths[name]) != digest for name, digest in hashes.items()):
        raise ValueError("Fonte MERGE ou Nível I mudou durante a execução do Nível II.")


def page_provenance(source, level1, result, mask, protection_source, occurrences,
                    consumed, lineage, lineage_paths):
    paths = {"source": source, "level1": level1, "result": result, "mask": mask}
    hashes = {name: consumed[name] for name in consumed}
    hashes.update({name: sha256(paths[name]) for name in ("result", "mask")})
    row = {f"{name}_sha256": digest for name, digest in hashes.items()}
    row["protection_source"] = dict(protection_source)
    row["protected_occurrence_ids"] = sorted(
        item["id"] for item in occurrences if isinstance(item.get("id"), str))
    row["protected_types_applied"] = sorted({
        item["tipo"] for item in occurrences if isinstance(item.get("tipo"), str)})
    row.update(lineage)
    captured = {name: (path, hashes[name]) for name, path in paths.items()}
    captured.update(lineage_paths)
    return row, captured


def assert_unchanged(records):
    for record in records:
        for path, expected in record.values():
            if sha256(Path(path)) != expected:
                raise ValueError("Artefato de origem mudou durante a execução do Nível II.")


def assert_report_artifacts_current(report, source_dir, level1_dir, output_dir):
    for row in report.get("pages", []):
        source = Path(source_dir) / row["source"]
        level1 = artifact_file(Path(level1_dir), row["level1_clean"], "clean")
        mask = artifact_file(Path(output_dir), row["mask"], "mask")
        result = (artifact_file(Path(output_dir), row["clean"], "clean")
                  if row.get("clean") else level1)
        expected = {"source": row["source_sha256"], "level1": row["level1_sha256"],
                    "result": row["result_sha256"], "mask": row["mask_sha256"]}
        paths = {"source": source, "level1": level1, "result": result, "mask": mask}
        if any(path is None or sha256(path) != expected[key]
               for key, path in paths.items()):
            raise ValueError("Artefatos do Nível II mudaram antes da publicação.")
        assert_level1_dependencies_current(Path(level1_dir), row)


def assert_level1_dependencies_current(folder, row):
    report_path = artifact_file(folder, "json/level1-balloon-report.json", "json")
    if report_path is None or sha256(report_path) != row["level1_report_sha256"]:
        raise ValueError("Relatório do Nível I mudou antes da publicação.")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    page = next((item for item in report.get("pages", [])
                 if isinstance(item, dict) and item.get("source") == row["source"]), None)
    if page is None:
        raise ValueError("Página ausente no relatório do Nível I.")
    label = artifact_file(folder, page.get("transparent_mask_artifact"), "mask")
    deferred_ref = page.get("deferred_text_mask_artifact")
    deferred = artifact_file(folder, deferred_ref, "mask") if deferred_ref else None
    if (label is None or sha256(label) != row["level1_mask_sha256"]
            or (deferred_ref and deferred is None)
            or (sha256(deferred) if deferred else None) != row.get("deferred_mask_sha256")):
        raise ValueError("Máscaras do Nível I mudaram antes da publicação.")
