"""Read and validate a Level II stage as the authoritative Level III input."""
import hashlib
from pathlib import Path

from PIL import Image

from processamento.unificacao_imagens.auto_merge.documentos import Document, read_document
from processamento.unificacao_imagens.auto_merge.nivel1 import read_level1


ALGORITHM = "merge_level2_bounded_safe_path_v1"


def _interval(item: object, total: int) -> tuple[int, int]:
    if not isinstance(item, dict):
        raise ValueError("Intervalo inválido no manifesto do Nível II.")
    start, end = item.get("global_start"), item.get("global_end")
    if type(start) is not int or type(end) is not int or not 0 <= start < end <= total:
        raise ValueError("Coordenadas inválidas no manifesto do Nível II.")
    return start, end


def _artifacts(items: object, directory: Path, total: int) -> list[dict]:
    if not isinstance(items, list):
        raise ValueError("Lista de artefatos do Nível II inválida.")
    result, names = [], set()
    for item in items:
        start, end = _interval(item, total)
        name = item.get("file")
        if not isinstance(name, str) or Path(name).name != name or name in names:
            raise ValueError("Nome de artefato do Nível II inválido.")
        path = directory / name
        if not path.resolve().is_relative_to(directory.resolve()) or not path.is_file():
            raise ValueError("Artefato do Nível II ausente.")
        with Image.open(path) as image:
            if image.height != end - start:
                raise ValueError("Dimensão incompatível no artefato do Nível II.")
            width = image.width
        names.add(name)
        result.append({**item, "file": name, "global_start": start,
                       "global_end": end, "width": width})
    return result


def _pending(items: object, total: int) -> list[dict]:
    if not isinstance(items, list):
        raise ValueError("Lista residual do Nível II inválida.")
    result = []
    for item in items:
        start, end = _interval(item, total)
        result.append({**item, "global_start": start, "global_end": end})
    return result


def _validate_partition(parents: list[dict], artifacts: list[dict], pending: list[dict]) -> None:
    children = artifacts + pending
    assigned = set()
    for parent in parents:
        start, end = parent["global_start"], parent["global_end"]
        parts = sorted((item for item in children
                        if item["global_start"] < end and item["global_end"] > start),
                       key=lambda item: item["global_start"])
        cursor = start
        for item in parts:
            marker = id(item)
            if marker in assigned or item["global_start"] != cursor or item["global_end"] > end:
                raise ValueError("Nível II possui lacuna, sobreposição ou intervalo fora do residual I.")
            assigned.add(marker)
            cursor = item["global_end"]
        if cursor != end:
            raise ValueError("Nível II não recompõe integralmente o residual do Nível I.")
    if len(assigned) != len(children):
        raise ValueError("Nível II contém intervalo fora dos resíduos do Nível I.")


def read_level2(manga: Path, chapter: str) -> Document:
    """Return a validated Level II document, including its Level I provenance."""
    directory = manga / "FLUXO_SECUNDARIO" / "01_MERGE_PROCESSAMENTO" / "MERGE_LEVEL2" / chapter
    record = read_document(directory / "merge-level2-manifest.json", manga)
    if record.status != "recorded":
        return record
    level1 = read_level1(manga, chapter)
    if level1.status != "recorded" or level1.data.get("kind") != "partial":
        return Document("invalid", error="O manifesto do Nível I não autoriza o Nível III.")
    level1_path = manga / "FLUXO_SECUNDARIO" / "01_MERGE_PROCESSAMENTO" / "AUTO_MERGE" / chapter / "auto-merge-manifest.json"
    try:
        data = record.data
        if data.get("algorithm") != ALGORITHM or data.get("schema_version") != 3:
            raise ValueError("Formato de registro do Nível II não suportado.")
        if data.get("chapter") != chapter or type(data.get("total_height")) is not int:
            raise ValueError("Manifesto do Nível II incompatível com o capítulo.")
        total = data["total_height"]
        if total != level1.data["total_height"]:
            raise ValueError("A altura do Nível II diverge do Nível I.")
        if data.get("source_level1_sha256") != hashlib.sha256(level1_path.read_bytes()).hexdigest():
            raise ValueError("O manifesto do Nível II está desatualizado em relação ao Nível I.")
        artifacts = _artifacts(data.get("artifacts"), directory, total)
        pending = _pending(data.get("pending_segments"), total)
        _validate_partition(level1.data["residuals"], artifacts, pending)
        return Document("recorded", {"total_height": total, "artifacts": artifacts,
                                      "residuals": pending, "algorithm": ALGORITHM})
    except (OSError, ValueError) as exc:
        return Document("invalid", error=str(exc))
