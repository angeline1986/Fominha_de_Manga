"""Read Level III only when its upstream provenance and partition are valid."""
import hashlib
from pathlib import Path

from PIL import Image

from processamento.unificacao_imagens.auto_merge.documentos import Document, read_document
from processamento.unificacao_imagens.auto_merge.nivel2 import read_level2


ALGORITHM = "merge_level3_structural_safe_v1"


def _entries(items, directory: Path, total: int, *, artifacts: bool) -> list[dict]:
    if not isinstance(items, list):
        raise ValueError("Lista do manifesto do Nível III inválida.")
    result, names = [], set()
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("Intervalo inválido no manifesto do Nível III.")
        start, end = item.get("global_start"), item.get("global_end")
        if type(start) is not int or type(end) is not int or not 0 <= start < end <= total:
            raise ValueError("Coordenadas inválidas no manifesto do Nível III.")
        row = {**item, "global_start": start, "global_end": end}
        if artifacts:
            name = item.get("file")
            if not isinstance(name, str) or Path(name).name != name or name in names:
                raise ValueError("Nome de artefato do Nível III inválido.")
            path = directory / name
            if not path.resolve().is_relative_to(directory.resolve()) or not path.is_file():
                raise ValueError("Artefato do Nível III ausente.")
            with Image.open(path) as image:
                if image.height != end - start:
                    raise ValueError("Dimensão incompatível no artefato do Nível III.")
                row["width"] = image.width
            names.add(name)
        result.append(row)
    return result


def _partition(parents: list[dict], children: list[dict]) -> None:
    used = set()
    for parent in parents:
        start, end = parent["global_start"], parent["global_end"]
        parts = sorted((item for item in children
                        if item["global_start"] < end and item["global_end"] > start),
                       key=lambda item: item["global_start"])
        cursor = start
        for item in parts:
            if id(item) in used or item["global_start"] != cursor or item["global_end"] > end:
                raise ValueError("Nível III possui lacuna, sobreposição ou intervalo fora do residual II.")
            used.add(id(item))
            cursor = item["global_end"]
        if cursor != end:
            raise ValueError("Nível III não recompõe integralmente o residual do Nível II.")
    if len(used) != len(children):
        raise ValueError("Nível III contém intervalo fora dos resíduos do Nível II.")


def read_level3(manga: Path, chapter: str) -> Document:
    directory = manga / "FLUXO_SECUNDARIO" / "01_MERGE_PROCESSAMENTO" / "MERGE_LEVEL3" / chapter
    path = directory / "merge-level3-manifest.json"
    record = read_document(path, manga)
    if record.status != "recorded":
        return record
    level2 = read_level2(manga, chapter)
    if level2.status != "recorded":
        return Document("invalid", error="Manifestos dos Níveis I e II não autorizam o Nível IV.")
    level2_path = manga / "FLUXO_SECUNDARIO" / "01_MERGE_PROCESSAMENTO" / "MERGE_LEVEL2" / chapter / "merge-level2-manifest.json"
    try:
        data = record.data
        total = data.get("total_height")
        if data.get("algorithm") != ALGORITHM or data.get("schema_version") != 1:
            raise ValueError("Formato de registro do Nível III não suportado.")
        if data.get("chapter") != chapter or type(total) is not int or total != level2.data["total_height"]:
            raise ValueError("Manifesto do Nível III incompatível com o capítulo.")
        if data.get("source_level2_sha256") != hashlib.sha256(level2_path.read_bytes()).hexdigest():
            raise ValueError("Manifesto do Nível III desatualizado em relação ao Nível II.")
        safe = _entries(data.get("safe_artifacts"), directory, total, artifacts=True)
        pending = _entries(data.get("residual_pending_segments"), directory, total, artifacts=False)
        _partition(level2.data["residuals"], safe + pending)
        return Document("recorded", {"total_height": total, "safe_artifacts": safe,
                                      "residuals": pending, "algorithm": ALGORITHM})
    except (OSError, ValueError) as exc:
        return Document("invalid", error=str(exc))
