"""Reuse verified composition bundles or invoke the composition engine."""
import json
from pathlib import Path

from central_v2.backend.operational_log import emit
from central_v2.backend.orchestration.textoff_merged.auto_cleaner_check_manifest import manifest_path
from central_v2.backend.orchestration.textoff_merged.artifact_paths import json_file
from central_v2.backend.orchestration.textoff_special.artifacts import sha256
from .composition import compose_page


def _compose_or_reuse(manga, provider, chapter, page, level1, output, solids, glass, mask,
                      solid_validation, glass_validation):
    bundle = output / f"{chapter}-{Path(page).stem}-combo"
    report_path, image_path = bundle / "report.json", bundle / "composed.png"
    if report_path.is_file() or bundle.exists():
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
            check = manifest_path(manga, chapter)
            level1_manifest = json_file(level1.parent.parent, "clean-manifest.json")
            validations = {}
            if solids:
                validations["SOLIDOS"] = solid_validation
            if glass:
                validations["GLASS"] = glass_validation
            hashes_match = (
                report.get("source_level1_sha256") == sha256(level1)
                and report.get("source_solids_sha256") == (sha256(solids) if solids else None)
                and report.get("source_glass_sha256") == (sha256(glass) if glass else None)
                and report.get("mask_sha256") == (sha256(mask) if mask else None)
                and report.get("check_manifest_sha256") == (sha256(check) if check.is_file() else None)
                and report.get("level1_manifest_sha256") == (sha256(level1_manifest) if level1_manifest.is_file() else None)
                and report.get("validations") == validations
                and report.get("provider") == provider and report.get("manga") == Path(manga).name
                and report.get("chapter") == chapter and report.get("page") == page
                and report.get("status") == "COMPOSED" and image_path.is_file()
                and report.get("result_sha256") == sha256(image_path))
            if hashes_match:
                return {**report, "output_dir": str(bundle), "result_path": str(image_path),
                        "report_path": str(report_path), "reused": True, "reasons": []}
        except (OSError, ValueError, TypeError):
            pass
    return compose_page(manga, provider, chapter, page, level1_path=level1,
        output_dir=output, solids_path=solids, glass_path=glass, mask_path=mask)
