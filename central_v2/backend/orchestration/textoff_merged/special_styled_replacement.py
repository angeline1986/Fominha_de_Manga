"""Replace one Artístico occurrence from its proved pre-filter input."""
from pathlib import Path

import cv2
import numpy as np

from central_v2.backend.orchestration.textoff_special.artifacts import contained_file, sha256
from central_v2.backend.orchestration.textoff_special.catalog import STAGING_ROOT

from . import special_styled_composition as composition
from .special_styled_authorship import different, image
from .stages import stage_chapter


def _mask(path, digest, shape):
    if path is None:
        raise ValueError("Máscara de autoria Artístico ausente.")
    path = Path(path)
    composition._require_hash(path, digest, "Máscara de autoria Artístico divergente.")
    value = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if value is None or value.shape != shape or not np.all((value == 0) | (value == 255)):
        raise ValueError("Máscara de autoria Artístico incompatível.")
    return value > 0


def compose_occurrence(manga, chapter, page, detection, current_path, current_hash,
                       final_record, run, destination):
    folder = Path(run.get("run_dir") or (STAGING_ROOT / run["run_id"])).resolve()
    technical = contained_file(folder, run.get("result_file"))
    mask_name = ((run.get("treatment") or {}).get("artifacts") or {}).get("authorized_mask")
    mask_ref = f"treatment/{mask_name}"
    authorized_path = contained_file(folder, mask_ref)
    composition._require_hash(authorized_path, (run.get("artifacts") or {}).get(mask_ref),
                              "Máscara autorizada Artístico divergente.")
    composition._require_hash(Path(detection["path"]), detection["sha256"],
                              "Snapshot histórico Artístico divergente.")
    composition._require_hash(Path(detection["prior_output"]), detection["prior_output_sha256"],
                              "Resultado Artístico anterior divergente.")
    composition._require_hash(technical, (run.get("validation") or {}).get("result_sha256"),
                              "Resultado técnico Artístico divergente.")
    successors = composition._verify_lineage(Path(manga), chapter, page, final_record,
                                             current_hash, detection["prior_output_sha256"])
    current_path = Path(current_path)
    composition._require_hash(current_path, current_hash, "Consolidado Final mudou.")
    before, old_page, after, current = (image(path) for path in (
        detection["path"], detection["prior_output"], technical, current_path))
    if any(value.shape != before.shape for value in (old_page, after, current)):
        raise ValueError("Dimensões incompatíveis impedem substituição Artístico.")
    shape = before.shape[:2]
    authorized = _mask(authorized_path, (run.get("artifacts") or {})[mask_ref], shape)
    occurrence = detection.get("occurrence") or {}
    old = _mask(occurrence.get("mask_path"), occurrence.get("mask_sha256"), shape)
    old_write = _mask(occurrence.get("write_mask_path", occurrence.get("mask_path")),
                      occurrence.get("write_mask_sha256", occurrence.get("mask_sha256")), shape)
    new = different(after, before)
    if np.any(new & ~authorized):
        raise ValueError("Resultado Artístico alterou pixels fora da máscara autorizada.")
    if np.any(old & ~old_write) or np.any(old & ~different(old_page, before)):
        raise ValueError("Autoria antiga Artístico não corresponde ao resultado histórico.")
    for other in occurrence.get("other_masks", []):
        other_write = _mask(other["path"], other["sha256"], shape)
        if np.any((authorized | old_write) & other_write):
            raise ValueError("Composição Artístico bloqueada: autoria compartilhada com outra ocorrência.")
    candidate = old | new
    later = different(current, old_page)
    overlap = int(np.count_nonzero(candidate & later))
    if overlap:
        raise ValueError(f"Composição Artístico bloqueada: {overlap} pixels sobrepostos a tratamento posterior.")
    dependencies = list(detection.get("dependencies", []))
    for successor in successors or []:
        if not isinstance(successor.get("write_mask"), dict):
            raise ValueError("Tratamento posterior sem máscara de autoria; publicação bloqueada.")
        dependencies.append({"stage": successor["stage"], "run_id": successor["run_id"],
                             "write_mask": successor["write_mask"]})
    for dependency in dependencies:
        stage = dependency.get("stage")
        info = dependency.get("write_mask") or {}
        if stage not in {"PINCEL_DEGRADE", "PINCEL_SUAVE"}:
            raise ValueError("Dependência posterior Artístico sem estágio verificável.")
        root = stage_chapter(Path(manga), stage, chapter, read_legacy=False).resolve()
        ref = info.get("artifact")
        path = (root / ref).resolve() if isinstance(ref, str) else root
        if (not isinstance(ref, str) or Path(ref).is_absolute() or ".." in Path(ref).parts
                or not path.is_relative_to(root / "authorship")):
            raise ValueError("Máscara de tratamento posterior ausente ou fora do estágio.")
        downstream = _mask(path, info.get("sha256"), shape)
        if np.any((old_write | authorized) & downstream):
            raise ValueError("Composição Artístico bloqueada: máscara de tratamento posterior sobreposta.")
    result = current.copy()
    result[old] = before[old]
    result[new] = after[new]
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(destination), result):
        raise RuntimeError("Não foi possível gravar substituição Artístico.")
    if sha256(current_path) != current_hash:
        destination.unlink(missing_ok=True)
        raise ValueError("Consolidado Final mudou durante composição Artístico.")
    return {"base_sha256": current_hash, "prior_artistic_sha256": detection["prior_output_sha256"],
            "technical_sha256": sha256(technical), "old_changed_pixels": int(old.sum()),
            "new_changed_pixels": int(new.sum()), "restored_pixels": int((old & ~new).sum()),
            "later_changed_pixels": int(later.sum()), "overlap_pixels": overlap,
            "dependencies": dependencies, "composed_sha256": sha256(destination)}
