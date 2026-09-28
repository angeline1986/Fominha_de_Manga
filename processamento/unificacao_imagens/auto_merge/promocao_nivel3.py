"""Promote a complete I + II + III composition without rerendering stages."""
import hashlib
import json
from pathlib import Path

from PIL import Image

from processamento.unificacao_imagens import image_stitcher as v3
from processamento.unificacao_imagens.auto_merge.nivel1 import read_level1
from processamento.unificacao_imagens.auto_merge.nivel2 import read_level2
from processamento.unificacao_imagens.auto_merge.persistencia_nivel1 import (
    copy_file_exclusive, write_json_exclusive,
)


def _pieces(directory: Path, items: list, source: str) -> list[dict]:
    result = []
    for item in items:
        name = item.get("file")
        start, end = item.get("global_start"), item.get("global_end")
        if (not isinstance(name, str) or Path(name).name != name
                or type(start) is not int or type(end) is not int or end <= start):
            raise ValueError("Artefato inválido na composição do Nível III.")
        path = directory / name
        if not path.is_file():
            raise ValueError("Artefato ausente na composição do Nível III.")
        with Image.open(path) as image:
            image.load()
            if image.height != end - start:
                raise ValueError("Dimensão incompatível na composição do Nível III.")
            width = image.width
        result.append({"source": path, "file": name, "start": start,
                       "end": end, "width": width, "source_stage": source})
    return result


def promote_level3(chapter: Path, level3: dict, level3_dir: Path) -> Path:
    if level3.get("residual_pending_segments"):
        raise ValueError("Há residual pendente; a promoção do MERGE foi bloqueada.")
    manga, name = chapter.parent.parent, chapter.name
    level1 = read_level1(manga, name)
    level2 = read_level2(manga, name)
    if level1.status != "recorded" or level2.status != "recorded":
        raise ValueError("Os manifestos dos Níveis I e II não são válidos.")
    level2_dir = manga / "FLUXO_SECUNDARIO" / "01_MERGE_PROCESSAMENTO" / "MERGE_LEVEL2" / name
    level2_file = level2_dir / "merge-level2-manifest.json"
    level3_file = level3_dir / "merge-level3-manifest.json"
    if level3.get("source_level2_sha256") != hashlib.sha256(level2_file.read_bytes()).hexdigest():
        raise ValueError("O manifesto do Nível III está desatualizado em relação ao Nível II.")
    if level3.get("chapter") != name or level3.get("total_height") != level2.data["total_height"]:
        raise ValueError("O manifesto do Nível III não corresponde ao capítulo.")

    level1_dir = manga / "FLUXO_SECUNDARIO" / "01_MERGE_PROCESSAMENTO" / "AUTO_MERGE" / name
    level1_manifest = json.loads((level1_dir / "auto-merge-manifest.json").read_text(encoding="utf-8"))
    level2_manifest = json.loads(level2_file.read_text(encoding="utf-8"))
    level1_file = level1_dir / "auto-merge-manifest.json"
    if (level2_manifest.get("source_level1_sha256")
            != hashlib.sha256(level1_file.read_bytes()).hexdigest()):
        raise ValueError("O manifesto do Nível II está desatualizado em relação ao Nível I.")
    first = _pieces(level1_dir, level1_manifest.get("artifacts", []), "auto_merge")
    second = _pieces(level2_dir, level2_manifest.get("artifacts", []), "level2")
    third = _pieces(level3_dir, level3.get("safe_artifacts", []), "level3")
    residuals = level3.get("residual_pending_segments")
    if not isinstance(residuals, list):
        raise ValueError("Lista residual do Nível III inválida.")
    pending_children = []
    for item in residuals:
        start, end = item.get("global_start"), item.get("global_end")
        if type(start) is not int or type(end) is not int or end <= start:
            raise ValueError("Intervalo residual do Nível III inválido.")
        pending_children.append({"start": start, "end": end})
    children = third + pending_children
    assigned = set()
    for parent in level2.data["residuals"]:
        parent_start, parent_end = parent["global_start"], parent["global_end"]
        parts = sorted((item for item in children
                        if item["start"] < parent_end and item["end"] > parent_start),
                       key=lambda item: item["start"])
        cursor = parent_start
        for item in parts:
            if id(item) in assigned or item["start"] != cursor or item["end"] > parent_end:
                raise ValueError("Nível III não recompõe exatamente os resíduos do Nível II.")
            assigned.add(id(item))
            cursor = item["end"]
        if cursor != parent_end:
            raise ValueError("Nível III não recompõe exatamente os resíduos do Nível II.")
    if len(assigned) != len(children):
        raise ValueError("Nível III contém intervalo fora dos resíduos do Nível II.")
    pieces = sorted(first + second + third, key=lambda item: item["start"])
    cursor, width = 0, None
    for item in pieces:
        if item["start"] != cursor or (width is not None and item["width"] != width):
            raise ValueError("Composição I + II + III contém lacuna, sobreposição ou largura incompatível.")
        cursor, width = item["end"], item["width"]
    if cursor != int(level3["total_height"]):
        raise ValueError("Composição I + II + III não cobre a altura total.")

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
            outputs.append({"file": item["file"], "global_start": item["start"],
                            "global_end": item["end"], "width": item["width"],
                            "height": item["end"] - item["start"],
                            "source_stage": item["source_stage"]})
        write_json_exclusive(official / "merge-manifest.json", {
            "schema_version": 1, "algorithm": "merge_auto_level2_level3_composition_v2",
            "status": "approved", "source_dir": str(chapter), "output_dir": str(official),
            "source_total_height": cursor, "merged_images": len(outputs), "outputs": outputs,
            "validation": {"ok": True, "errors": [], "coverage_start": 0, "coverage_end": cursor},
            "safety": {"source_files_modified": False, "stage_artifacts_rerendered": False},
            "composition": {"scope": "level3_all_safe", "level1_manifest": "auto-merge-manifest.json",
                            "level2_manifest": "merge-level2-manifest.json",
                            "level3_manifest": "merge-level3-manifest.json"},
            "provenance": {"level2_sha256": hashlib.sha256(level2_file.read_bytes()).hexdigest(),
                           "level3_sha256": hashlib.sha256(level3_file.read_bytes()).hexdigest()},
        })
        created.append(official / "merge-manifest.json")
        if not v3.is_chapter_merged(chapter):
            raise ValueError("MERGE oficial não foi reconhecido após a promoção.")
    except Exception:
        for path in created:
            path.unlink(missing_ok=True)
        official.rmdir()
        raise
    return official
