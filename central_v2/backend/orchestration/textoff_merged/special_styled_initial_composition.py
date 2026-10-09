"""Assess effective Artístico writes against the current page and later authors."""
import json
from pathlib import Path

import cv2
import numpy as np

from central_v2.backend.orchestration.textoff_special.artifacts import contained_file, sha256
from central_v2.backend.orchestration.textoff_special.catalog import STAGING_ROOT

from .artifact_paths import artifact_ref
from .stages import stage_chapter

STAGES = {"PINCEL_DEGRADE": ("PINCEL_DEGRADE", "degrade-manifest.json"),
          "PINCEL_SUAVE": ("PINCEL_SUAVE", "suave-manifest.json")}


def _image(path):
    value = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if value is None:
        raise ValueError("Imagem de composição Artístico inválida.")
    return value


def _write_mask(manga, chapter, page, row, shape):
    stage, name = STAGES[row["origin"]]
    folder = stage_chapter(manga, stage, chapter, read_legacy=False).resolve()
    manifest = folder / artifact_ref("json", name)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    candidates = [(payload.get("pages") or {}).get(page)]
    for group in payload.get("superseded_results", []):
        candidates += [item.get("record") for item in group.get("pages", [])
                       if item.get("page") == page]
    matches = [item for item in candidates if isinstance(item, dict)
               and item.get("run_id") == row.get("run_id")
               and (item.get("output") or {}).get("sha256") == row.get("sha256")]
    if len(matches) != 1:
        raise ValueError("Autoria de tratamento posterior ausente.")
    output_ref = (matches[0].get("output") or {}).get("artifact")
    output = (folder / output_ref).resolve() if isinstance(output_ref, str) else folder
    verified_output = (isinstance(output_ref, str) and not Path(output_ref).is_absolute()
                       and ".." not in Path(output_ref).parts
                       and output.is_relative_to(folder / "clean")
                       and output.is_file() and sha256(output) == row["sha256"])
    if not verified_output:
        for group in payload.get("superseded_results", []):
            for item in group.get("pages", []):
                if item.get("record") != matches[0]:
                    continue
                for archived in item.get("archived_artifacts", []):
                    ref = archived.get("artifact")
                    path = (folder / ref).resolve() if isinstance(ref, str) else folder
                    if (isinstance(ref, str) and not Path(ref).is_absolute()
                            and ".." not in Path(ref).parts
                            and path.is_relative_to(folder / "archive")
                            and path.is_file() and archived.get("sha256") == row["sha256"]
                            and sha256(path) == row["sha256"]):
                        verified_output = True
    if not verified_output:
        raise ValueError("Resultado de tratamento posterior sem SHA verificável.")
    info = matches[0].get("write_mask") or {}
    ref = info.get("artifact")
    path = (folder / ref).resolve() if isinstance(ref, str) else folder
    if (not isinstance(ref, str) or Path(ref).is_absolute() or ".." in Path(ref).parts
            or not path.is_relative_to(folder / "authorship") or not path.is_file()
            or sha256(path) != info.get("sha256")):
        raise ValueError("Máscara de autoria posterior sem SHA verificável.")
    mask = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if mask is None or mask.shape != shape or not np.all((mask == 0) | (mask == 255)):
        raise ValueError("Máscara de autoria posterior incompatível.")
    return mask > 0, {"stage": stage, "run_id": row["run_id"],
                      "mask_sha256": info["sha256"]}


def compose_initial(manga, chapter, page, detection, current_path, current_record,
                    run, destination):
    """Write a composed candidate only when ancestry and masks prove it safe."""
    folder = Path(run.get("run_dir") or (STAGING_ROOT / run["run_id"])).resolve()
    technical = contained_file(folder, run["result_file"])
    mask_ref = "treatment/roi_authorized_mask.png"
    authorized_path = contained_file(folder, mask_ref)
    if (sha256(technical) != (run.get("validation") or {}).get("result_sha256")
            or sha256(authorized_path) != (run.get("artifacts") or {}).get(mask_ref)
            or sha256(Path(detection["path"])) != detection["sha256"]
            or sha256(current_path) != current_record["sha256"]):
        raise ValueError("SHA da entrada, máscara ou resultado Artístico divergente.")
    before, after, current = map(_image, (detection["path"], technical, current_path))
    authorized = cv2.imread(str(authorized_path), cv2.IMREAD_GRAYSCALE)
    if (before.shape != after.shape or before.shape != current.shape
            or authorized is None or authorized.shape != before.shape[:2]):
        raise ValueError("Dimensões Artístico incompatíveis para composição.")
    changed = before != after if before.ndim == 2 else np.any(before != after, axis=2)
    if np.any(changed & (authorized == 0)):
        raise ValueError("Resultado Artístico alterou pixels fora da máscara autorizada.")
    final_manifest = stage_chapter(manga, "CONSOLIDADO_FINAL", chapter) / "json/final-manifest.json"
    final_hash = sha256(final_manifest)
    final = json.loads(final_manifest.read_text(encoding="utf-8"))
    rows = [item["superseded"] for item in final.get("history", [])
            if item.get("page") == page and isinstance(item.get("superseded"), dict)]
    rows.append(current_record)
    positions = [i for i, row in enumerate(rows) if row.get("sha256") == detection["sha256"]]
    candidate_rows = rows[positions[-1] + 1:] if positions else rows
    masks, proofs = [], []
    for row in candidate_rows:
        if row.get("origin") in STAGES:
            value, proof = _write_mask(manga, chapter, page, row, changed.shape)
            masks.append(value); proofs.append(proof)
    downstream = np.logical_or.reduce(masks) if masks else np.zeros_like(changed)
    conflict = changed & downstream
    report = {"source_sha256": detection["sha256"], "current_sha256": current_record["sha256"],
              "technical_sha256": sha256(technical), "authorized_mask_sha256": sha256(authorized_path),
              "effective_write_pixels": int(changed.sum()),
              "downstream_write_pixels": int(downstream.sum()),
              "conflict_pixels": int(conflict.sum()), "downstream_masks": proofs}
    for name, value in (("effective", changed), ("downstream", downstream),
                        ("conflict", conflict)):
        path = folder / f"initial_{name}_write_mask.png"
        if not cv2.imwrite(str(path), value.astype(np.uint8) * 255):
            raise RuntimeError("Falha ao registrar máscara de composição Artístico.")
        report[f"{name}_write_mask_sha256"] = sha256(path)
    (folder / "initial_composition.json").write_text(json.dumps(report, indent=2) + "\n")
    if conflict.any():
        raise ValueError(f"Composição Artístico bloqueada: {report['conflict_pixels']} pixels em conflito.")
    if not positions:
        raise ValueError("Linhagem da entrada do Check até o Consolidado Final não comprovada.")
    successors = rows[positions[-1] + 1:]
    previous = detection["sha256"]
    for row in successors:
        if row.get("origin") not in STAGES or row.get("input_sha256") != previous:
            raise ValueError("Linhagem de tratamento posterior incompleta.")
        previous = row["sha256"]
    if previous != current_record["sha256"]:
        raise ValueError("Linhagem Artístico não alcança a versão final vigente.")
    composed = current.copy(); composed[changed] = after[changed]
    destination = Path(destination); destination.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(destination), composed):
        raise RuntimeError("Falha ao gravar composição Artístico em staging.")
    if sha256(current_path) != current_record["sha256"] or sha256(final_manifest) != final_hash:
        destination.unlink(missing_ok=True)
        raise ValueError("Consolidado mudou durante a composição Artístico.")
    report["composed_sha256"] = sha256(destination)
    (folder / "initial_composition.json").write_text(json.dumps(report, indent=2) + "\n")
    return report
