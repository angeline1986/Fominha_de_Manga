"""Read the Level I record without recomputing residuals or validating pixels."""
from pathlib import Path

from processamento.unificacao_imagens.auto_merge.documentos import (
    Document, artifact_exists, read_document,
)


ALGORITHMS = {
    "auto_merge_level1_complete": "complete",
    "auto_merge_level1_resolved_segments": "partial",
}


def _interval(item: object, total: int) -> dict:
    if not isinstance(item, dict):
        raise ValueError("Intervalo inválido no registro.")
    start, end = item.get("global_start"), item.get("global_end")
    if type(start) is not int or type(end) is not int or not 0 <= start < end <= total:
        raise ValueError("Coordenadas inválidas no registro.")
    return {"global_start": start, "global_end": end}


def read_level1(manga: Path, chapter: str) -> Document:
    directory = manga / "FLUXO_SECUNDARIO" / "01_MERGE_PROCESSAMENTO" / "AUTO_MERGE" / chapter
    record = read_document(directory / "auto-merge-manifest.json", manga)
    if record.status != "recorded":
        return record
    data = record.data
    algorithm = data.get("algorithm")
    if not isinstance(algorithm, str) or algorithm not in ALGORITHMS:
        return Document("unsupported", error="Algoritmo do registro do Nível I não suportado.")
    if type(data.get("schema_version")) is not int or data["schema_version"] != 1:
        return Document("unsupported", error="Formato de registro do Nível I não suportado.")
    try:
        if data.get("chapter") != chapter:
            raise ValueError("O registro pertence a outro capítulo.")
        total = data.get("total_height")
        if type(total) is not int or total <= 0:
            raise ValueError("Altura total inválida no registro.")
        artifacts, pending = data.get("artifacts"), data.get("pending_segments")
        if not isinstance(artifacts, list) or not isinstance(pending, list):
            raise ValueError("Listas de artefatos ou residual inválidas.")
        files, names = [], set()
        for item in artifacts:
            interval = _interval(item, total)
            name = item.get("file")
            if not isinstance(name, str) or not name or Path(name).name != name or name in {".", ".."} or name in names:
                raise ValueError("Nome de artefato inválido ou repetido.")
            names.add(name)
            files.append({**interval, "file": name, "exists": artifact_exists(directory, name)})
        residuals = [_interval(item, total) for item in pending]
        reasons = sorted({
            item.get("reason") for item in pending
            if isinstance(item.get("reason"), str) and item.get("reason")
        })
        kind = ALGORITHMS[algorithm]
        if kind == "complete" and (residuals or not files):
            raise ValueError("Registro completo sem artefatos ou com residual.")
        return Document("recorded", {
            "kind": kind, "artifacts": files, "residuals": residuals,
            "total_height": total, "algorithm": data["algorithm"],
            "reason_codes": reasons,
        })
    except ValueError as exc:
        return Document("invalid", error=str(exc))


def read_attempt(manga: Path, chapter: str) -> Document:
    path = manga / "FLUXO_SECUNDARIO" / "01_MERGE_PROCESSAMENTO" / "MERGE_STATUS" / chapter / "merge-attempt.json"
    record = read_document(path, manga)
    if record.status != "recorded":
        return record
    data = record.data
    if data.get("chapter") != chapter or not isinstance(data.get("message"), str):
        return Document("invalid", error="Registro de tentativa inválido.")
    return Document("recorded", {"message": data["message"]})


def read_official(manga: Path, chapter: str) -> Document:
    path = manga / "FLUXO_SECUNDARIO" / "02_MERGE" / chapter / "merge-manifest.json"
    record = read_document(path, manga)
    if record.status != "recorded":
        return record
    data = record.data
    if not isinstance(data.get("algorithm"), str) or not isinstance(data.get("outputs"), list):
        return Document("invalid", error="Registro do MERGE oficial inválido.")
    # Presence is deliberately not a claim of physical integrity or current authority.
    return Document("recorded", {"algorithm": data["algorithm"], "outputs_count": len(data["outputs"])})
