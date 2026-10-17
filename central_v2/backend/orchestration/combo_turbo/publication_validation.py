"""Fail-closed validation of isolated Combo results and publication inputs."""
import json
from pathlib import Path
import tempfile

from central_v2.backend.orchestration.textoff_special.artifacts import sha256
from central_v2.backend.orchestration.textoff_merged.auto_cleaner_check_manifest import manifest_path
from central_v2.backend.orchestration.textoff_merged.final_consolidated import final_manifest_path
from central_v2.backend.orchestration.textoff_merged.final_consolidated_manifest import read_manifest
from central_v2.backend.orchestration.textoff_merged.manifests import _stage_manifest_sha256
from central_v2.backend.orchestration.textoff_merged.stages import LEVEL1, provider_name, stage_chapter
from .models import image_size, valid_page_id
from .run_result_store import SCHEMA
from .validation import validate_page


def validate_run(manga, run_root, chapter, result):
    manga, run_root = Path(manga).resolve(), Path(run_root).resolve()
    workspace = _isolated_workspace(manga, run_root, chapter)
    provider = workspace["provider"]
    if (not isinstance(result, dict) or result.get("schema") != SCHEMA
            or result.get("version") != 1 or result.get("mode") != "ISOLATED_RUN"
            or result.get("status") not in {"COMPLETED", "PARTIAL"}):
        raise ValueError("Resultado Combo não publicável.")
    if (result.get("run_id") != workspace.get("run_id")
            or result.get("provider") != provider or result.get("manga") != manga.name
            or result.get("chapters") != workspace.get("chapters")
            or result.get("source_signature") != workspace.get("signature")
            or result.get("workspace_root") != str(run_root)):
        raise ValueError("Identidade do resultado Combo diverge do workspace.")
    rows = [item for item in result.get("results", [])
            if isinstance(item, dict) and item.get("chapter") == chapter]
    if len(rows) != 1 or rows[0].get("status") not in {"COMPLETED", "PARTIAL"}:
        raise ValueError("Resultado do capítulo ausente ou incompleto.")
    pages = {}
    for item in rows[0].get("pages", []):
        if not isinstance(item, dict):
            raise ValueError("Registro de página Combo inválido.")
        page = item.get("page")
        if not valid_page_id(page) or page in pages:
            raise ValueError("Página Combo ausente ou duplicada.")
        pages[page] = _validate_page(manga, run_root, provider, chapter, item)
    if not pages:
        raise ValueError("Resultado Combo sem páginas para validar.")
    logical = stage_chapter(manga, "TO_MERGED_CONSOLIDADO", chapter, read_legacy=False)
    final = stage_chapter(manga, "CONSOLIDADO_FINAL", chapter, read_legacy=False)
    logical_manifest = logical / "json" / "clean-manifest.json"
    final_manifest = final / "json" / "final-manifest.json"
    logical_hash = sha256(logical_manifest) if logical_manifest.is_file() else None
    final_hash = sha256(final_manifest) if final_manifest.is_file() else None
    final_payload = read_manifest(final_manifest, manga, chapter) if final_hash else None
    for page, row in pages.items():
        old = (final_payload or {}).get("pages", {}).get(page)
        if old and old.get("origin") in {"PINCEL_ARTISTICO", "PINCEL_DEGRADE", "PINCEL_SUAVE"}:
            row["status"] = "BLOCKED"
            row["reasons"] = ["SPECIAL_TREATMENT_PRESENT"]
            row["preserved_final_sha256"] = old.get("sha256")
    return {"pages": pages, "logical_hash": logical_hash, "final_hash": final_hash,
            "final_payload": final_payload, "logical_manifest": logical_manifest,
            "final_manifest": final_manifest}


def _isolated_workspace(manga, run_root, chapter):
    allowed = {Path(tempfile.gettempdir()).resolve(), Path("/tmp").resolve(),
               Path("/private/tmp").resolve()}
    marker = run_root / ".combo-workspace.json"
    try:
        data = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError) as exc:
        raise ValueError("Marcador de workspace isolado ausente ou inválido.") from exc
    source = Path(data.get("source", "")).resolve()
    if (not any(run_root.is_relative_to(root) for root in allowed)
            or manga != run_root / ".combo-workspace" / source.name
            or not manga.is_dir() or manga.is_symlink() or source == manga
            or chapter not in data.get("chapters", [])
            or data.get("provider") != source.parent.name):
        raise ValueError("Publicação permitida somente no snapshot isolado.")
    if not isinstance(data.get("chapters"), list) or not data.get("run_id"):
        raise ValueError("Identidade da execução no workspace é inválida.")
    from .execution import source_signature
    if source_signature(source, data["provider"], data["chapters"]) != data.get("signature"):
        raise ValueError("Fontes operacionais mudaram desde a cópia isolada.")
    return data


def _validate_page(manga, run_root, provider, chapter, item):
    page, composition = item["page"], item.get("composition") or {}
    status = item.get("status", composition.get("status"))
    if status in {"NO_WORK", "CONFLICT", "BLOCKED", "FAILED", "INVALID"}:
        underlying = {status, "INVALID", "FAILED"}
        if status == "FAILED":
            underlying.add("NO_WORK")
        if composition.get("status") not in underlying:
            raise ValueError(f"Estado persistido diverge da composição para {page}.")
        return {"page": page, "status": status,
                "reasons": item.get("reasons", composition.get("reasons", [])),
                "conflict_pixels": item.get("conflict_pixels", composition.get("overlap_pixels", 0)),
                "mask_sha256": item.get("mask_sha256", composition.get("mask_sha256"))}
    if status != "COMPOSED" or composition.get("status") != "COMPOSED":
        raise ValueError(f"Estado Combo inválido para {page}.")
    image = Path(composition.get("result_path", "")).resolve()
    report_path = Path(composition.get("report_path", "")).resolve()
    if (not image.is_relative_to(run_root) or not report_path.is_relative_to(run_root)
            or not image.is_file() or not report_path.is_file()
            or sha256(image) != composition.get("result_sha256")):
        raise ValueError(f"Imagem ou relatório Combo inválido para {page}.")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if any(report.get(key) != composition.get(key) for key in (
            "stage", "provider", "manga", "chapter", "page", "status",
            "result_sha256", "source_level1_sha256", "source_solids_sha256",
            "source_glass_sha256", "mask_sha256", "check_manifest_sha256",
            "level1_manifest_sha256", "validations", "overlap_pixels")):
        raise ValueError(f"Relatório Combo não confere com a execução para {page}.")
    if (report.get("stage") != "COMBO_TURBO" or report.get("status") != "COMPOSED"
            or report.get("provider") != provider or report.get("manga") != manga.name
            or report.get("chapter") != chapter or report.get("page") != page
            or report.get("overlap_pixels") != 0 or report.get("promoted") is not False):
        raise ValueError(f"Composição não está apta para publicação: {page}.")
    check = manifest_path(manga, chapter)
    level1_manifest = stage_chapter(manga, LEVEL1, chapter) / "json" / "clean-manifest.json"
    level1_image = stage_chapter(manga, LEVEL1, chapter) / "clean" / f"{Path(page).stem}_clean.png"
    if (not check.is_file() or not level1_manifest.is_file() or not level1_image.is_file()
            or sha256(check) != report.get("check_manifest_sha256")
            or sha256(level1_manifest) != report.get("level1_manifest_sha256")
            or sha256(level1_image) != report.get("source_level1_sha256")
            or image_size(image) != image_size(level1_image)):
        raise ValueError(f"Check, Nível I ou dimensões divergentes para {page}.")
    _validate_sources(manga, provider, chapter, page, report)
    return {**report, "page": page, "status": "COMPOSED", "image": str(image),
            "report_file": str(report_path), "report_sha256": sha256(report_path),
            "image_size": image_size(image), "reasons": []}


def _validate_sources(manga, provider, chapter, page, report):
    expected = report.get("validations")
    if not isinstance(expected, dict):
        raise ValueError(f"Validações de origem ausentes para {page}.")
    for stage, field in (("SOLIDOS", "source_solids_sha256"), ("GLASS", "source_glass_sha256")):
        if report.get(field) is None:
            if stage in expected:
                raise ValueError(f"Proveniência {stage} inesperada para {page}.")
            continue
        current = validate_page(manga, provider, chapter, page, stage)
        if (current.get("status") != "REUSABLE" or current != expected.get(stage)
                or current.get("artifact_sha256") != report[field]):
            raise ValueError(f"Dependência {stage} obsoleta ou inválida para {page}.")


def validate_published_page(manga, chapter, page, expected_sha256=None):
    """Resolve a current Combo image only while its lineage still validates."""
    from .publication_manifest import read_manifest, path_for
    if not valid_page_id(page):
        return None
    folder = path_for(manga, chapter)
    try:
        folder = folder.resolve()
        if folder.is_symlink() or not folder.is_relative_to(Path(manga).resolve()):
            return None
        manifest = read_manifest(manga, chapter)
        row = manifest["pages"].get(page)
        if not isinstance(row, dict) or row.get("status") != "COMPOSED":
            return None
        image = _safe_reference(folder, row.get("artifact"))
        report_file = _safe_reference(folder, row.get("report"))
        if (image is None or report_file is None or sha256(image) != row.get("sha256")
                or (expected_sha256 is not None and row.get("sha256") != expected_sha256)
                or sha256(report_file) != row.get("report_sha256")):
            return None
        report = json.loads(report_file.read_text(encoding="utf-8"))
        if report.get("result_sha256") != row["sha256"] or report.get("page") != page:
            return None
        if (sha256(manifest_path(manga, chapter)) != row.get("check_manifest_sha256")
                or _stage_manifest_sha256(manga, LEVEL1, chapter) != row.get("level1_manifest_sha256")):
            return None
        from central_v2.backend.orchestration.textoff_merged.final_consolidated import final_manifest_path
        from central_v2.backend.orchestration.textoff_merged.final_consolidated_manifest import read_manifest
        final_path = final_manifest_path(manga, chapter)
        if final_path.is_file():
            final = read_manifest(final_path, manga, chapter)
            current = final.get("pages", {}).get(page, {})
            if current.get("origin") in {"PINCEL_ARTISTICO", "PINCEL_DEGRADE", "PINCEL_SUAVE"}:
                return None
        _validate_sources(manga, provider_name(manga), chapter, page, row)
        level1_image = stage_chapter(manga, LEVEL1, chapter) / "clean" / f"{Path(page).stem}_clean.png"
        if image_size(image) != image_size(level1_image):
            return None
        return {**row, "path": image, "manifest_sha256": sha256(folder / "json/combo-manifest.json")}
    except (OSError, ValueError, TypeError, KeyError):
        return None

def _safe_reference(folder, reference):
    raw = folder / reference if isinstance(reference, str) else folder
    if (not isinstance(reference, str) or Path(reference).is_absolute()
            or ".." in Path(reference).parts or raw.is_symlink()):
        return None
    path = (folder / reference).resolve()
    if not path.is_relative_to(folder.resolve()) or path.is_symlink() or not path.is_file():
        return None
    return path
