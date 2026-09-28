"""Promote complete I + II + III + IV artifacts without rerendering them."""
import hashlib
import json
from pathlib import Path

from PIL import Image

from processamento.unificacao_imagens import image_stitcher as v3
from processamento.unificacao_imagens.auto_merge.nivel1 import read_level1
from processamento.unificacao_imagens.auto_merge.nivel2 import read_level2
from processamento.unificacao_imagens.auto_merge.nivel3 import read_level3
from processamento.unificacao_imagens.auto_merge.persistencia_nivel1 import (
    copy_file_exclusive, write_json_exclusive,
)


def _pieces(directory: Path, rows: list, source: str) -> list[dict]:
    result = []
    for row in rows:
        name, start, end = row.get("file"), row.get("global_start"), row.get("global_end")
        if not isinstance(name, str) or Path(name).name != name or type(start) is not int or type(end) is not int or end <= start:
            raise ValueError("Artefato inválido na composição do Nível IV.")
        path = directory / name
        if not path.resolve().is_relative_to(directory.resolve()) or not path.is_file():
            raise ValueError("Artefato ausente na composição do Nível IV.")
        with Image.open(path) as image:
            if image.height != end - start:
                raise ValueError("Dimensão incompatível na composição do Nível IV.")
            width = image.width
        result.append({"source": path, "file": name, "start": start, "end": end,
                       "width": width, "source_stage": source})
    return result


def promote_level4(chapter: Path, manifest: dict, level4_dir: Path) -> Path:
    if manifest.get("residual_pending_segments"):
        raise ValueError("Há residual pendente; a promoção do MERGE foi bloqueada.")
    manga, name = chapter.parent.parent, chapter.name
    level1, level2, level3 = read_level1(manga, name), read_level2(manga, name), read_level3(manga, name)
    if any(item.status != "recorded" for item in (level1, level2, level3)):
        raise ValueError("Manifestos dos Níveis I a III não autorizam a promoção.")
    l3dir = manga / "FLUXO_SECUNDARIO" / "01_MERGE_PROCESSAMENTO" / "MERGE_LEVEL3" / name
    l3path = l3dir / "merge-level3-manifest.json"
    l4path = level4_dir / "merge-level4-manifest.json"
    if manifest.get("algorithm") != "merge_level4_directed_structural_safe_v1" or manifest.get("chapter") != name:
        raise ValueError("Manifesto do Nível IV incompatível com o capítulo.")
    if manifest.get("total_height") != level3.data["total_height"]:
        raise ValueError("Altura total do Nível IV diverge dos estágios anteriores.")
    l3_hash = hashlib.sha256(l3path.read_bytes()).hexdigest()
    if manifest.get("source_level3_sha256") != l3_hash:
        raise ValueError("Manifesto do Nível IV desatualizado em relação ao Nível III.")
    l1dir = manga / "FLUXO_SECUNDARIO" / "01_MERGE_PROCESSAMENTO" / "AUTO_MERGE" / name
    l2dir = manga / "FLUXO_SECUNDARIO" / "01_MERGE_PROCESSAMENTO" / "MERGE_LEVEL2" / name
    l1data = json.loads((l1dir / "auto-merge-manifest.json").read_text(encoding="utf-8"))
    l2data = json.loads((l2dir / "merge-level2-manifest.json").read_text(encoding="utf-8"))
    l3data = json.loads(l3path.read_text(encoding="utf-8"))
    first = _pieces(l1dir, l1data.get("artifacts", []), "auto_merge")
    second = _pieces(l2dir, l2data.get("artifacts", []), "level2")
    third = _pieces(l3dir, l3data.get("safe_artifacts", []), "level3")
    fourth = _pieces(level4_dir, manifest.get("safe_artifacts", []), "level4")
    pending = manifest.get("residual_pending_segments")
    if not isinstance(pending, list):
        raise ValueError("Residual do Nível IV inválido.")
    children = [{"global_start": row["start"], "global_end": row["end"]}
                for row in fourth]
    children.extend({"global_start": row.get("global_start"), "global_end": row.get("global_end")}
                    for row in pending)
    used = set()
    for parent in level3.data["residuals"]:
        start, end = parent["global_start"], parent["global_end"]
        parts = sorted((row for row in children if row["global_start"] < end and row["global_end"] > start),
                       key=lambda row: row["global_start"])
        cursor = start
        for row in parts:
            if id(row) in used or row["global_start"] != cursor or row["global_end"] > end:
                raise ValueError("Nível IV não recompõe exatamente os resíduos do Nível III.")
            used.add(id(row)); cursor = row["global_end"]
        if cursor != end:
            raise ValueError("Nível IV não recompõe exatamente os resíduos do Nível III.")
    if len(used) != len(children):
        raise ValueError("Nível IV contém intervalo fora dos resíduos do Nível III.")
    pieces = sorted(first + second + third + fourth, key=lambda row: row["start"])
    cursor, width = 0, None
    for row in pieces:
        if row["start"] != cursor or (width is not None and row["width"] != width):
            raise ValueError("Composição I + II + III + IV contém lacuna, sobreposição ou largura incompatível.")
        cursor, width = row["end"], row["width"]
    if cursor != manifest["total_height"]:
        raise ValueError("Composição I + II + III + IV não cobre a altura total.")
    official = v3.merge_output_dir(chapter)
    if official.exists():
        raise FileExistsError("Destino MERGE oficial ocupado; promoção cancelada.")
    official.mkdir(parents=True, exist_ok=False)
    created = []
    try:
        outputs = []
        for row in pieces:
            destination = official / row["file"]
            copy_file_exclusive(row["source"], destination); created.append(destination)
            outputs.append({"file": row["file"], "global_start": row["start"],
                            "global_end": row["end"], "width": row["width"],
                            "height": row["end"] - row["start"], "source_stage": row["source_stage"]})
        write_json_exclusive(official / "merge-manifest.json", {
            "schema_version": 1, "algorithm": "merge_auto_level2_level3_level4_composition_v1",
            "status": "approved", "source_dir": str(chapter), "output_dir": str(official),
            "source_total_height": cursor, "merged_images": len(outputs), "outputs": outputs,
            "validation": {"ok": True, "errors": [], "coverage_start": 0, "coverage_end": cursor},
            "safety": {"source_files_modified": False, "stage_artifacts_rerendered": False},
            "composition": {"scope": "level4_all_safe", "level1_manifest": "auto-merge-manifest.json",
                            "level2_manifest": "merge-level2-manifest.json", "level3_manifest": "merge-level3-manifest.json",
                            "level4_manifest": "merge-level4-manifest.json"},
            "provenance": {"level3_sha256": l3_hash,
                            "level4_sha256": hashlib.sha256(l4path.read_bytes()).hexdigest()},
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
