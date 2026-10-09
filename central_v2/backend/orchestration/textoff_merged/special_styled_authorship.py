"""Record and verify effective Artístico writes for each approved occurrence."""
from hashlib import sha256 as hash_bytes
from pathlib import Path
import shutil

import cv2
import numpy as np

from central_v2.backend.orchestration.textoff_special.artifacts import sha256


def image(path):
    value = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if value is None or value.ndim not in {2, 3}:
        raise ValueError("Imagem de autoria Artístico inválida.")
    return value


def different(left, right):
    if left.shape != right.shape:
        raise ValueError("Imagens Artístico incompatíveis para autoria.")
    return left != right if left.ndim == 2 else np.any(left != right, axis=2)


def _inside(roi, shape):
    try:
        x, y, w, h = (roi[key] for key in ("x", "y", "width", "height"))
    except (KeyError, TypeError):
        raise ValueError("ROI Artístico sem coordenadas aprovadas.") from None
    if (any(type(v) not in (int, float) for v in (x, y, w, h))
            or x < 0 or y < 0 or w <= 0 or h <= 0 or x + w > shape[1] or y + h > shape[0]):
        raise ValueError("ROI Artístico fora da imagem histórica.")
    region = np.zeros(shape, dtype=bool)
    region[int(y):int(y + h), int(x):int(x + w)] = True
    return region


def masks(source, technical, authorized, ids, rois):
    """Partition verified authorized components; shared components remain ambiguous."""
    before, after = image(source), image(technical)
    mask = cv2.imread(str(authorized), cv2.IMREAD_GRAYSCALE)
    if (mask is None or mask.shape != before.shape[:2] or before.shape != after.shape
            or len(ids) != len(rois) or len(set(ids)) != len(ids)):
        raise ValueError("Entrada, máscara ou identidades Artístico incompatíveis.")
    changed = different(before, after)
    active = mask > 0
    if np.any(changed & ~active):
        raise ValueError("Resultado Artístico fora da máscara autorizada.")
    regions = [_inside(roi, active.shape) for roi in rois]
    labels_count, labels = cv2.connectedComponents(active.astype(np.uint8), connectivity=8)
    writes = {identity: np.zeros(active.shape, dtype=bool) for identity in ids}
    ambiguous = set()
    for label in range(1, labels_count):
        component = labels == label
        owners = [identity for identity, region in zip(ids, regions)
                  if np.any(component & region)]
        if len(owners) == 1:
            writes[owners[0]] |= component
        else:
            ambiguous.update(owners or ids)
    if np.any(changed & ~np.logical_or.reduce(list(writes.values()))):
        ambiguous.update(ids)
    return {identity: {"write": writes[identity], "changed": writes[identity] & changed,
                       "ambiguous": identity in ambiguous} for identity in ids}


def persist(staged, source, technical, authorized, ids, rois, run_id):
    source, technical = Path(source), Path(technical)
    ownership = masks(source, technical, authorized, ids, rois)
    technical_ref = f"authorship/{run_id}/technical.png"
    technical_copy = staged / technical_ref
    technical_copy.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(technical, technical_copy)
    if sha256(technical_copy) != sha256(technical):
        raise ValueError("Resultado técnico por ocorrência Artístico divergente.")
    result = {}
    for identity, roi in zip(ids, rois):
        value = ownership[identity]
        if value["ambiguous"]:
            result[identity] = {"roi": roi, "run_id": run_id,
                                "status": "ambiguous"}
            continue
        stem = hash_bytes(identity.encode("utf-8")).hexdigest()[:20]
        record = {"roi": roi, "run_id": run_id, "status": "verified",
                  "input_sha256": sha256(source), "technical_sha256": sha256(technical),
                  "technical_output": {"artifact": technical_ref,
                                       "sha256": sha256(technical_copy)}}
        for name in ("write", "changed"):
            ref = f"authorship/{run_id}/{stem}-{name}.png"
            target = staged / ref
            target.parent.mkdir(parents=True, exist_ok=True)
            if not cv2.imwrite(str(target), value[name].astype(np.uint8) * 255):
                raise RuntimeError("Não foi possível persistir autoria Artístico.")
            record[f"{name}_mask"] = {"artifact": ref, "sha256": sha256(target)}
        result[identity] = record
    return result


def verified(folder, record, identity, roi, input_hash):
    folder = Path(folder).resolve()
    if (not isinstance(record, dict) or record.get("status") != "verified"
            or record.get("roi") != roi or record.get("input_sha256") != input_hash):
        raise ValueError(f"Autoria histórica Artístico insuficiente para {identity}.")
    found = {}
    technical = record.get("technical_output") or {}
    technical_ref = technical.get("artifact")
    technical_path = (folder / technical_ref).resolve() if isinstance(technical_ref, str) else folder
    if (not isinstance(technical_ref, str) or Path(technical_ref).is_absolute()
            or ".." in Path(technical_ref).parts
            or not technical_path.is_relative_to(folder / "authorship")
            or not technical_path.is_file()
            or sha256(technical_path) != technical.get("sha256")
            or technical.get("sha256") != record.get("technical_sha256")):
        raise ValueError(f"Resultado técnico histórico Artístico inválido para {identity}.")
    for name in ("write", "changed"):
        info = record.get(f"{name}_mask") or {}
        ref = info.get("artifact")
        relative = Path(ref) if isinstance(ref, str) else Path()
        path = (folder / relative).resolve()
        if (not isinstance(ref, str) or relative.is_absolute() or ".." in relative.parts
                or not path.is_relative_to(folder / "authorship") or not path.is_file()
                or sha256(path) != info.get("sha256")):
            raise ValueError(f"Máscara de autoria Artístico inválida para {identity}.")
        found[name] = path
    return found
