"""Promote complete I–V compositions while preserving stage artifacts."""
import hashlib
import json
from pathlib import Path

from PIL import Image

from processamento.unificacao_imagens import image_stitcher as v3
from processamento.unificacao_imagens.auto_merge.nivel1 import read_level1
from processamento.unificacao_imagens.auto_merge.nivel2 import read_level2
from processamento.unificacao_imagens.auto_merge.nivel3 import read_level3
from processamento.unificacao_imagens.auto_merge.nivel4 import read_level4
from processamento.unificacao_imagens.auto_merge.persistencia_nivel1 import (
    copy_file_exclusive, write_json_exclusive,
)


def _pieces(directory: Path, rows: list, stage: str) -> list[dict]:
    result = []
    for row in rows:
        name, start, end = row.get("file"), row.get("global_start"), row.get("global_end")
        if not isinstance(name, str) or Path(name).name != name or type(start) is not int or type(end) is not int or end <= start:
            raise ValueError("Artefato inválido na composição do Nível V.")
        path = directory / name
        if not path.resolve().is_relative_to(directory.resolve()) or not path.is_file():
            raise ValueError("Artefato ausente na composição do Nível V.")
        with Image.open(path) as image:
            if image.height != end - start:
                raise ValueError("Dimensão incompatível na composição do Nível V.")
            width = image.width
        result.append({"source": path, "file": name, "start": start, "end": end,
                       "width": width, "source_stage": stage})
    return result


def promote_level5(chapter: Path, manifest: dict, level5_dir: Path) -> Path:
    if manifest.get("residual_pending_segments"):
        raise ValueError("Há residual pendente; a promoção do MERGE foi bloqueada.")
    manga, name = chapter.parent.parent, chapter.name
    documents = [read_level1(manga, name), read_level2(manga, name),
                 read_level3(manga, name), read_level4(manga, name)]
    if any(document.status != "recorded" for document in documents):
        raise ValueError("Manifestos dos Níveis I a IV não autorizam a promoção.")
    first_level4 = documents[-1].data
    l4dir = manga / "FLUXO_SECUNDARIO" / "01_MERGE_PROCESSAMENTO" / "MERGE_LEVEL4" / name
    l4path = l4dir / "merge-level4-manifest.json"
    l5path = level5_dir / "merge-level5-manifest.json"
    if manifest.get("algorithm") != "merge_level5_global_structural_safe_v1" or manifest.get("chapter") != name:
        raise ValueError("Manifesto do Nível V incompatível com o capítulo.")
    if manifest.get("total_height") != first_level4["total_height"]:
        raise ValueError("Altura total do Nível V diverge dos estágios anteriores.")
    l4hash = hashlib.sha256(l4path.read_bytes()).hexdigest()
    if manifest.get("source_level4_sha256") != l4hash:
        raise ValueError("Manifesto do Nível V desatualizado em relação ao Nível IV.")
    base = manga / "FLUXO_SECUNDARIO" / "01_MERGE_PROCESSAMENTO"
    l1dir, l2dir = base / "AUTO_MERGE" / name, base / "MERGE_LEVEL2" / name
    l3dir = base / "MERGE_LEVEL3" / name
    l1data = json.loads((l1dir / "auto-merge-manifest.json").read_text(encoding="utf-8"))
    l2data = json.loads((l2dir / "merge-level2-manifest.json").read_text(encoding="utf-8"))
    l3data = json.loads((l3dir / "merge-level3-manifest.json").read_text(encoding="utf-8"))
    l4data = json.loads(l4path.read_text(encoding="utf-8"))
    pieces = (_pieces(l1dir, l1data.get("artifacts", []), "auto_merge")
              + _pieces(l2dir, l2data.get("artifacts", []), "level2")
              + _pieces(l3dir, l3data.get("safe_artifacts", []), "level3")
              + _pieces(l4dir, l4data.get("safe_artifacts", []), "level4")
              + _pieces(level5_dir, manifest.get("safe_artifacts", []), "level5"))
    residuals = manifest.get("residual_pending_segments")
    if not isinstance(residuals, list):
        raise ValueError("Residual do Nível V inválido.")
    children = [{"global_start": item["start"], "global_end": item["end"]}
                for item in pieces if item["source_stage"] == "level5"]
    children.extend({"global_start": row.get("global_start"), "global_end": row.get("global_end")}
                    for row in residuals)
    used = set()
    for parent in first_level4["residuals"]:
        start, end = parent["global_start"], parent["global_end"]
        rows = sorted((row for row in children if row["global_start"] < end and row["global_end"] > start),
                      key=lambda row: row["global_start"])
        cursor = start
        for row in rows:
            if id(row) in used or row["global_start"] != cursor or row["global_end"] > end:
                raise ValueError("Nível V não recompõe exatamente os resíduos do Nível IV.")
            used.add(id(row)); cursor = row["global_end"]
        if cursor != end:
            raise ValueError("Nível V não recompõe exatamente os resíduos do Nível IV.")
    if len(used) != len(children):
        raise ValueError("Nível V contém intervalo fora dos resíduos do Nível IV.")
    pieces.sort(key=lambda item: item["start"])
    cursor, width = 0, None
    for item in pieces:
        if item["start"] != cursor or (width is not None and item["width"] != width):
            raise ValueError("Composição I–V contém lacuna, sobreposição ou largura incompatível.")
        cursor, width = item["end"], item["width"]
    if cursor != manifest["total_height"]:
        raise ValueError("Composição I–V não cobre a altura total.")
    official = v3.merge_output_dir(chapter)
    if official.exists():
        raise FileExistsError("Destino MERGE oficial ocupado; promoção cancelada.")
    official.mkdir(parents=True, exist_ok=False); created = []
    try:
        outputs = []
        for item in pieces:
            destination = official / item["file"]
            copy_file_exclusive(item["source"], destination); created.append(destination)
            outputs.append({"file": item["file"], "global_start": item["start"],
                            "global_end": item["end"], "width": item["width"],
                            "height": item["end"] - item["start"], "source_stage": item["source_stage"]})
        write_json_exclusive(official / "merge-manifest.json", {
            "schema_version": 1, "algorithm": "merge_auto_level2_level3_level4_level5_composition_v1",
            "status": "approved", "source_dir": str(chapter), "output_dir": str(official),
            "source_total_height": cursor, "merged_images": len(outputs), "outputs": outputs,
            "validation": {"ok": True, "errors": [], "coverage_start": 0, "coverage_end": cursor},
            "safety": {"source_files_modified": False, "stage_artifacts_rerendered": False},
            "composition": {"scope": "level5_all_safe", "level1_manifest": "auto-merge-manifest.json",
                            "level2_manifest": "merge-level2-manifest.json", "level3_manifest": "merge-level3-manifest.json",
                            "level4_manifest": "merge-level4-manifest.json", "level5_manifest": "merge-level5-manifest.json"},
            "provenance": {"level4_sha256": l4hash,
                            "level5_sha256": hashlib.sha256(l5path.read_bytes()).hexdigest()},
        })
        created.append(official / "merge-manifest.json")
        if not v3.is_chapter_merged(chapter):
            raise ValueError("MERGE oficial não foi reconhecido após a promoção.")
    except Exception:
        for path in created:
            path.unlink(missing_ok=True)
        official.rmdir(); raise
    return official
