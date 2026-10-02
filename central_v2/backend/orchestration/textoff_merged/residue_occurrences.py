"""Persistence and validation for human-reviewed TextOff residue occurrences."""
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import tempfile

SCHEMA = "textoff_residue_occurrence_manifest_v1"
MANIFEST_NAME = "residue-occurrences-manifest.json"
TYPE_LABELS = {
    "residuo_transparencia": "Resíduo de transparência",
    "residuo_degrade": "Resíduo do degradê",
    "residuo_gradiente": "Resíduo do gradiente",
    "fragmento_balao": "Fragmento de balão",
    "texto_residual": "Texto residual",
    "outro": "Outro defeito",
}


def validate_occurrences(raw, natural_width: int, natural_height: int) -> list[dict]:
    if not isinstance(raw, list) or not raw:
        raise ValueError("Adicione pelo menos uma ocorrência antes de catalogar.")
    if natural_width <= 0 or natural_height <= 0:
        raise ValueError("Dimensões da imagem processada inválidas.")
    result, ids = [], set()
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("Ocorrência inválida.")
        occurrence_id, number, kind = item.get("id"), item.get("number"), item.get("type")
        if not isinstance(occurrence_id, str) or not occurrence_id or len(occurrence_id) > 128 or occurrence_id in ids:
            raise ValueError("Identificador de ocorrência inválido ou repetido.")
        if type(number) is not int or number <= 0:
            raise ValueError("Número de ocorrência inválido.")
        if not isinstance(kind, str) or kind not in TYPE_LABELS:
            raise ValueError("Tipo de ocorrência inválido.")
        box = item.get("box_normalized")
        if not isinstance(box, dict):
            raise ValueError("Coordenadas da ocorrência inválidas.")
        values = {key: _finite_number(box.get(key)) for key in ("left", "top", "width", "height")}
        left, top, width, height = (values[key] for key in ("left", "top", "width", "height"))
        if (left < 0 or top < 0 or left > 1 or top > 1 or width <= 0 or height <= 0
                or width > 1 or height > 1 or left + width > 1 or top + height > 1):
            raise ValueError("A área selecionada ultrapassa os limites da imagem.")
        note = item.get("note")
        if kind == "outro":
            if not isinstance(note, str) or not note.strip():
                raise ValueError("Descreva o defeito classificado como Outro.")
            note = note.strip()
        else:
            note = None
        result.append({
            "id": occurrence_id, "numero": number, "tipo": kind,
            "label": TYPE_LABELS[kind], "observacao": note,
            "box_normalized": values,
            "box_pixels": {"x": round(left * natural_width), "y": round(top * natural_height),
                           "width": round(width * natural_width), "height": round(height * natural_height)},
        })
        ids.add(occurrence_id)
    return result


def empty_manifest(document: dict) -> dict:
    return {"schema": SCHEMA,
            "meta": {"versao": 1, "atualizado_em": datetime.now(timezone.utc).isoformat()},
            "documento": dict(document), "pages": {}}


def read_manifest(path: Path, document: dict) -> dict:
    if not path.exists():
        return empty_manifest(document)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("O manifesto de ocorrências existente não pôde ser lido.") from exc
    existing_document = payload.get("documento") if isinstance(payload, dict) else None
    if (not isinstance(payload, dict) or payload.get("schema") != SCHEMA
            or not isinstance(payload.get("pages"), dict) or not isinstance(existing_document, dict)
            or existing_document.get("provider") != document["provider"]
            or existing_document.get("obra") != document["obra"]
            or existing_document.get("capitulo") != document["capitulo"]):
        raise ValueError("O manifesto de ocorrências existente tem estrutura incompatível.")
    return payload


def occurrences_for(manifest: dict, page: str, step: str) -> list[dict]:
    page_record = manifest.get("pages", {}).get(page, {})
    steps = page_record.get("steps", {}) if isinstance(page_record, dict) else {}
    record = steps.get(step, {}) if isinstance(steps, dict) else {}
    occurrences = record.get("ocorrencias", []) if isinstance(record, dict) else []
    return occurrences if isinstance(occurrences, list) else []


def update_page(path: Path, document: dict, page: str, step: str, occurrences: list[dict]) -> dict:
    manifest = read_manifest(path, document)
    page_record = manifest["pages"].setdefault(page, {"steps": {}})
    if not isinstance(page_record, dict) or not isinstance(page_record.get("steps", {}), dict):
        raise ValueError("A entrada existente da página é inválida.")
    page_record.setdefault("steps", {})[step] = {
        "total_ocorrencias": len(occurrences), "ocorrencias": occurrences,
    }
    manifest["meta"] = {"versao": 1, "atualizado_em": datetime.now(timezone.utc).isoformat()}
    manifest["documento"] = {**document, "step": step}
    _write_atomic(path, manifest)
    return manifest


def _finite_number(value) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("Coordenada numérica inválida.")
    return float(value)


def _write_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write("\n"); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
