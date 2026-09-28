"""Validate and promote an I + II composition without rerendering artifacts."""
import json
from pathlib import Path

from PIL import Image

from processamento.unificacao_imagens import image_stitcher as v3
from processamento.unificacao_imagens.auto_merge.persistencia_nivel1 import (
    copy_file_exclusive,
    write_json_exclusive,
)


def _pieces(stage: Path, manifest: dict, source: str) -> list[dict]:
    result = []
    for item in manifest.get("artifacts", []):
        name = item.get("file")
        if not isinstance(name, str) or Path(name).name != name:
            raise ValueError("Nome de artefato inválido para promoção.")
        start, end = int(item["global_start"]), int(item["global_end"])
        path = stage / name
        if not path.is_file() or end <= start:
            raise ValueError("Artefato ausente ou intervalo inválido.")
        with Image.open(path) as image:
            image.load()
            if image.height != end - start:
                raise ValueError("Dimensão de artefato incompatível com o manifesto.")
            width = image.width
        result.append({"source": path, "file": name, "start": start, "end": end,
                       "width": width, "source_stage": source})
    return result


def promote_level2(chapter: Path, level1: dict, level1_dir: Path,
                   level2: dict, level2_dir: Path) -> Path:
    if level2.get("pending_segments"):
        raise ValueError("Há residual pendente; a promoção do MERGE foi bloqueada.")
    first = _pieces(level1_dir, level1, "auto_merge")
    second = _pieces(level2_dir, level2, "level2")
    pieces = sorted(first + second, key=lambda item: item["start"])
    cursor, width = 0, None
    for item in pieces:
        if item["start"] != cursor:
            raise ValueError("Composição I + II contém lacuna ou sobreposição.")
        if width is None:
            width = item["width"]
        elif item["width"] != width:
            raise ValueError("Composição I + II contém larguras incompatíveis.")
        cursor = item["end"]
    if cursor != int(level2["total_height"]):
        raise ValueError("Composição I + II não cobre a altura total.")

    official = v3.merge_output_dir(chapter)
    if official.exists():
        raise FileExistsError("Destino MERGE oficial ocupado; promoção cancelada.")
    official.mkdir(parents=True, exist_ok=False)
    created = []
    try:
        outputs = []
        for item in pieces:
            destination = official / item["file"]
            copy_file_exclusive(item["source"], destination)
            created.append(destination)
            outputs.append({
                "file": item["file"], "global_start": item["start"],
                "global_end": item["end"], "width": item["width"],
                "height": item["end"] - item["start"],
                "source_stage": item["source_stage"],
            })
        payload = {
            "schema_version": 1,
            "algorithm": "merge_auto_level2_composition_v2",
            "status": "approved", "source_dir": str(chapter),
            "output_dir": str(official), "source_total_height": cursor,
            "merged_images": len(outputs), "outputs": outputs,
            "validation": {"ok": True, "errors": [], "coverage_start": 0, "coverage_end": cursor},
            "safety": {"source_files_modified": False, "forced_cut_without_safe_band": False,
                       "stage_artifacts_rerendered": False},
            "composition": {"scope": "level2_complete", "level1_manifest": "auto-merge-manifest.json",
                            "level2_manifest": "merge-level2-manifest.json"},
        }
        write_json_exclusive(official / "merge-manifest.json", payload)
        created.append(official / "merge-manifest.json")
        if not v3.is_chapter_merged(chapter):
            raise ValueError("MERGE oficial não foi reconhecido após a promoção.")
    except Exception:
        for path in created:
            path.unlink(missing_ok=True)
        official.rmdir()
        raise
    return official
