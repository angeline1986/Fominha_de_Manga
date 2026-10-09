"""Validate an Artístico delta and compose it without overwriting later work."""
import json
from pathlib import Path

import cv2
import numpy as np

from central_v2.backend.orchestration.textoff_special.artifacts import contained_file, sha256
from central_v2.backend.orchestration.textoff_special.catalog import STAGING_ROOT
from .artifact_paths import artifact_ref
from .stages import stage_chapter

ORIGINS = {"PINCEL_DEGRADE": ("PINCEL_DEGRADE", "degrade-manifest.json"),
           "PINCEL_SUAVE": ("PINCEL_SUAVE", "suave-manifest.json"),
           "PINCEL_ARTISTICO": ("PINCEL_ARTISTICO", "artistico-manifest.json")}


def compose_delta(manga: Path, chapter: str, page: str, detection: dict,
                  current_path: Path, current_hash: str, final_record: dict,
                  run: dict, destination: Path) -> dict:
    folder = Path(run.get("run_dir") or (STAGING_ROOT / run["run_id"])).resolve()
    technical = contained_file(folder, run.get("result_file"))
    treatment = run.get("treatment") or {}
    artifacts = treatment.get("artifacts") or {}
    mask = contained_file(folder, f"treatment/{artifacts.get('authorized_mask', '')}")
    mask_ref = f"treatment/{artifacts.get('authorized_mask', '')}"
    if sha256(mask) != (run.get("artifacts") or {}).get(mask_ref):
        raise ValueError("Máscara autorizada Artístico divergente do manifesto da execução.")
    source = Path(detection["path"])
    previous = Path(detection["prior_output"])
    _require_hash(source, detection["sha256"], "Snapshot histórico Artístico divergente.")
    _require_hash(previous, detection["prior_output_sha256"], "Resultado Artístico anterior divergente.")
    _require_hash(technical, (run.get("validation") or {}).get("result_sha256"),
                  "Resultado técnico Artístico divergente.")
    _verify_lineage(Path(manga), chapter, page, final_record, current_hash,
                    detection["prior_output_sha256"])
    _require_hash(current_path, current_hash, "Consolidado Final mudou antes da composição.")
    original = _image(source)
    technical_image = _image(technical)
    prior = _image(previous)
    current = _image(current_path)
    authorized = cv2.imread(str(mask), cv2.IMREAD_GRAYSCALE)
    if (authorized is None or authorized.shape != original.shape[:2]
            or technical_image.shape != original.shape or prior.shape != original.shape
            or current.shape != original.shape):
        raise ValueError("Dimensões incompatíveis impedem a composição Artístico.")
    delta = _different_pixels(technical_image, original)
    if np.any(delta & (authorized == 0)):
        raise ValueError("Resultado Artístico alterou pixels fora da máscara autorizada.")
    later = _different_pixels(current, prior)
    overlap = int(np.count_nonzero(delta & later))
    if overlap:
        raise ValueError(f"Composição Artístico bloqueada: {overlap} pixels sobrepostos a tratamento posterior.")
    composed = current.copy()
    composed[delta] = technical_image[delta]
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(destination), composed):
        raise RuntimeError("Não foi possível gravar a composição Artístico.")
    if sha256(current_path) != current_hash:
        destination.unlink(missing_ok=True)
        raise ValueError("Consolidado Final mudou durante a composição Artístico.")
    return {"base_sha256": current_hash, "prior_artistic_sha256": detection["prior_output_sha256"],
            "technical_sha256": sha256(technical), "authorized_delta_pixels": int(delta.sum()),
            "later_changed_pixels": int(later.sum()), "overlap_pixels": overlap,
            "composed_sha256": sha256(destination)}


def _verify_lineage(manga, chapter, page, final_record, current_hash, artistic_hash):
    origin, digest = final_record.get("origin"), current_hash
    successors = []
    if origin == "PINCEL_ARTISTICO":
        if digest != artistic_hash:
            raise ValueError("Linhagem Artístico atual não corresponde ao resultado anterior.")
        return successors
    for _ in range(4):
        if origin not in ORIGINS or origin == "PINCEL_ARTISTICO":
            break
        stage, filename = ORIGINS[origin]
        record = _find_run_record(manga, chapter, page, stage, filename, digest,
                                  final_record.get("run_id") if origin == final_record.get("origin") else None)
        successors.append({"stage": stage, "run_id": record.get("run_id"),
                           "write_mask": record.get("write_mask")})
        input_hash = (record.get("input") or {}).get("sha256")
        input_artifact = (record.get("input_artifact") or {}).get("artifact")
        saved_input = _safe_artifact(stage_chapter(manga, stage, chapter, read_legacy=False),
                                     input_artifact, "input")
        if sha256(saved_input) != input_hash or record.get("selected_from") is None:
            raise ValueError("Snapshot intermediário da linhagem está inválido.")
        origin, digest = record["selected_from"], input_hash
        if origin == "PINCEL_ARTISTICO":
            if digest != artistic_hash:
                raise ValueError("Linhagem posterior não deriva do resultado Artístico registrado.")
            return successors
    raise ValueError("Linhagem posterior ao Artístico ausente ou não comprovável.")


def _find_run_record(manga, chapter, page, stage, filename, digest, run_id=None):
    folder = stage_chapter(manga, stage, chapter, read_legacy=False).resolve()
    manifest = folder / artifact_ref("json", filename)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    candidates = [((payload.get("pages") or {}).get(page) or {})]
    for group in payload.get("superseded_results", []):
        candidates.extend(item.get("record") or {} for item in group.get("pages", []))
    for record in candidates:
        output = record.get("output") or {}
        if output.get("sha256") != digest or (run_id and record.get("run_id") != run_id):
            continue
        path = _resolve_output(folder, record, payload)
        if sha256(path) == digest:
            return record
    raise ValueError(f"Manifesto {stage} não comprova a saída posterior.")


def _resolve_output(folder, record, payload):
    ref = (record.get("output") or {}).get("artifact")
    try:
        path = _safe_artifact(folder, ref, "clean")
        if path.is_file():
            return path
    except ValueError:
        pass
    for group in payload.get("superseded_results", []):
        for item in group.get("pages", []):
            if (item.get("record") or {}).get("output") == record.get("output"):
                for archived in item.get("archived_artifacts", []):
                    candidate = _safe_artifact(folder, archived.get("artifact"), "archive")
                    if candidate.is_file() and sha256(candidate) == archived.get("sha256"):
                        return candidate
    raise ValueError("Saída operacional da linhagem não está disponível.")


def _safe_artifact(folder, reference, section):
    relative = Path(reference) if isinstance(reference, str) else Path()
    path = (Path(folder) / relative).resolve()
    if (not isinstance(reference, str) or relative.is_absolute() or ".." in relative.parts
            or not path.is_relative_to(Path(folder).resolve() / section)):
        raise ValueError("Referência de artefato operacional inválida.")
    return path


def _require_hash(path, expected, message):
    if not isinstance(expected, str) or not Path(path).is_file() or sha256(path) != expected:
        raise ValueError(message)


def _image(path):
    image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if image is None:
        raise ValueError(f"Imagem inválida para composição: {path.name}.")
    if image.ndim not in {2, 3} or (image.ndim == 3 and image.shape[2] not in {3, 4}):
        raise ValueError(f"Formato de canais não suportado: {path.name}.")
    return image


def _different_pixels(left, right):
    if left.shape != right.shape:
        raise ValueError("Imagens incompatíveis para comparação Artístico.")
    return left != right if left.ndim == 2 else np.any(left != right, axis=2)


from .special_styled_replacement import compose_occurrence
