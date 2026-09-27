"""Persist Level I evidence and promote only complete validated compositions."""
from pathlib import Path

from PIL import Image

from processamento.unificacao_imagens import image_stitcher as v3
from processamento.unificacao_imagens.auto_merge.persistencia_nivel1 import (
    copy_file_exclusive, write_json_exclusive,
)
from processamento.unificacao_imagens.auto_merge.planejamento_nivel1 import (
    Level1Plan, validate_plan,
)


def _stage_manifest(chapter: Path, stage: Path, plan: Level1Plan, artifacts: list) -> dict:
    return {
        "schema_version": 1,
        "algorithm": "auto_merge_level1_complete" if plan.status == "complete"
        else "auto_merge_level1_resolved_segments",
        "chapter": chapter.name,
        "source_dir": str(chapter),
        "output_dir": str(stage),
        "total_height": plan.total_height,
        "artifacts": [
            {key: item[key] for key in ("file", "global_start", "global_end")}
            for item in artifacts
        ],
        "pending_segments": [
            {"global_start": item.start, "global_end": item.end, "reason": item.reason}
            for item in plan.intervals if item.status == "pending"
        ],
        "coverage": {
            "auto_segments": [[item.start, item.end] for item in plan.intervals if item.status == "safe"]
        },
    }


def write_stage_manifest(chapter: Path, plan: Level1Plan, artifacts: list) -> Path:
    validate_plan(plan)
    stage = chapter.parent.parent / "FLUXO_SECUNDARIO" / "01_MERGE_PROCESSAMENTO" / "AUTO_MERGE" / chapter.name
    manifest = stage / "auto-merge-manifest.json"
    write_json_exclusive(manifest, _stage_manifest(chapter, stage, plan, artifacts))
    return manifest


def _validated_artifacts(stage: Path, plan: Level1Plan, artifacts: list) -> list[dict]:
    expected_intervals = [(item.start, item.end) for item in plan.intervals]
    actual = sorted(artifacts, key=lambda item: item["global_start"])
    if [(item["global_start"], item["global_end"]) for item in actual] != expected_intervals:
        raise ValueError("Artefatos não correspondem à cobertura completa planejada.")
    validated = []
    for item in actual:
        name = item.get("file")
        if not isinstance(name, str) or Path(name).name != name:
            raise ValueError("Nome de artefato inválido.")
        source = (stage / name).resolve()
        if source.parent != stage.resolve() or not source.is_file():
            raise ValueError("Artefato ausente ou fora do estágio.")
        start, end = int(item["global_start"]), int(item["global_end"])
        with Image.open(source) as image:
            image.load()
            if image.width != int(item["width"]) or image.height != end - start:
                raise ValueError(f"Dimensões inválidas no artefato {name}.")
            width = image.width
        validated.append({
            "source": source, "file": name, "global_start": start,
            "global_end": end, "width": width, "height": end - start,
        })
    return validated


def promote_complete(chapter: Path, plan: Level1Plan, artifacts: list) -> Path:
    """Create the official MERGE without replacing any existing destination."""
    validate_plan(plan)
    if plan.status != "complete":
        raise ValueError("Somente uma composição completa pode ser promovida.")
    chapter = Path(chapter).resolve()
    official = v3.merge_output_dir(chapter)
    stage = chapter.parent.parent / "FLUXO_SECUNDARIO" / "01_MERGE_PROCESSAMENTO" / "AUTO_MERGE" / chapter.name
    outputs = _validated_artifacts(stage, plan, artifacts)
    if official.exists():
        raise FileExistsError("Destino MERGE oficial ocupado; promoção cancelada.")
    official.parent.mkdir(parents=True, exist_ok=True)
    official.mkdir(parents=True, exist_ok=False)
    created = []
    try:
        manifest_outputs = []
        for item in outputs:
            destination = official / item["file"]
            copy_file_exclusive(item["source"], destination)
            created.append(destination)
            manifest_outputs.append({key: item[key] for key in (
                "file", "global_start", "global_end", "width", "height",
            )})
        manifest = {
            "schema_version": 1,
            "algorithm": "merge_auto_level1_composition_v2",
            "status": "approved",
            "source_dir": str(chapter),
            "output_dir": str(official),
            "source_total_height": plan.total_height,
            "merged_images": len(manifest_outputs),
            "outputs": manifest_outputs,
            "validation": {"ok": True, "errors": [], "coverage_start": 0, "coverage_end": plan.total_height},
            "safety": {"source_files_modified": False, "forced_cut_without_white_band": False},
            "composition": {"scope": "level1_complete", "stage": str(stage)},
        }
        write_json_exclusive(official / "merge-manifest.json", manifest)
        created.append(official / "merge-manifest.json")
        if not v3.is_chapter_merged(chapter):
            raise ValueError("MERGE oficial não foi reconhecido após promoção.")
    except Exception:
        for path in created:
            path.unlink(missing_ok=True)
        official.rmdir()
        raise
    return official
