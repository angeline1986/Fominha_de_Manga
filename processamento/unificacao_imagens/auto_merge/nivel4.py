"""Read Level IV as authoritative input for Auto-Merge Level V."""
import hashlib
from pathlib import Path

from PIL import Image

from processamento.unificacao_imagens.auto_merge.documentos import Document, read_document
from processamento.unificacao_imagens.auto_merge.nivel3 import read_level3


ALGORITHM = "merge_level4_directed_structural_safe_v1"


def _rows(items: object, directory: Path, total: int, check_file: bool) -> list[dict]:
    if not isinstance(items, list):
        raise ValueError("Lista do manifesto do Nível IV inválida.")
    result, names = [], set()
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("Intervalo inválido no manifesto do Nível IV.")
        start, end = item.get("global_start"), item.get("global_end")
        if type(start) is not int or type(end) is not int or not 0 <= start < end <= total:
            raise ValueError("Coordenadas inválidas no manifesto do Nível IV.")
        row = {**item, "global_start": start, "global_end": end}
        if check_file:
            name = item.get("file")
            if not isinstance(name, str) or Path(name).name != name or name in names:
                raise ValueError("Nome de artefato do Nível IV inválido.")
            path = directory / name
            if not path.resolve().is_relative_to(directory.resolve()) or not path.is_file():
                raise ValueError("Artefato do Nível IV ausente.")
            with Image.open(path) as image:
                if image.height != end - start:
                    raise ValueError("Dimensão incompatível no artefato do Nível IV.")
                row["width"] = image.width
            names.add(name)
        result.append(row)
    return result


def _partition(parents: list[dict], children: list[dict]) -> None:
    used = set()
    for parent in parents:
        start, end = parent["global_start"], parent["global_end"]
        parts = sorted((row for row in children if row["global_start"] < end and row["global_end"] > start),
                       key=lambda row: row["global_start"])
        cursor = start
        for row in parts:
            if id(row) in used or row["global_start"] != cursor or row["global_end"] > end:
                raise ValueError("Nível IV possui lacuna, sobreposição ou intervalo fora do residual III.")
            used.add(id(row)); cursor = row["global_end"]
        if cursor != end:
            raise ValueError("Nível IV não recompõe integralmente o residual do Nível III.")
    if len(used) != len(children):
        raise ValueError("Nível IV contém intervalo fora dos resíduos do Nível III.")


def read_level4(manga: Path, chapter: str) -> Document:
    directory = manga / "FLUXO_SECUNDARIO" / "01_MERGE_PROCESSAMENTO" / "MERGE_LEVEL4" / chapter
    path = directory / "merge-level4-manifest.json"
    record = read_document(path, manga)
    if record.status != "recorded":
        return record
    level3 = read_level3(manga, chapter)
    if level3.status != "recorded":
        return Document("invalid", error="Manifestos anteriores não autorizam o Nível V.")
    level3_path = manga / "FLUXO_SECUNDARIO" / "01_MERGE_PROCESSAMENTO" / "MERGE_LEVEL3" / chapter / "merge-level3-manifest.json"
    try:
        data = record.data
        total = data.get("total_height")
        if data.get("algorithm") != ALGORITHM or data.get("schema_version") != 1:
            raise ValueError("Formato do manifesto do Nível IV não suportado para o Nível V.")
        if data.get("chapter") != chapter or type(total) is not int or total != level3.data["total_height"]:
            raise ValueError("Manifesto do Nível IV incompatível com o capítulo.")
        if data.get("source_level3_sha256") != hashlib.sha256(level3_path.read_bytes()).hexdigest():
            raise ValueError("Manifesto do Nível IV desatualizado em relação ao Nível III.")
        safe = _rows(data.get("safe_artifacts"), directory, total, True)
        pending = _rows(data.get("residual_pending_segments"), directory, total, False)
        _partition(level3.data["residuals"], safe + pending)
        return Document("recorded", {"total_height": total, "safe_artifacts": safe,
                                      "residuals": pending, "algorithm": ALGORITHM})
    except (OSError, ValueError) as exc:
        return Document("invalid", error=str(exc))
