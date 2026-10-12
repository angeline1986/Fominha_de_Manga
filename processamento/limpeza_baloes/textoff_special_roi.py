from pathlib import Path
import shutil
import json
import time
import cv2
import numpy as np

ALGORITHM = "textoff_special_roi_degrade_v2"

def run_degrade_roi(
    source: Path,
    target: Path,
    selections,
    base_snapshot: Path | None = None,
    approved_check_rois: bool = False,
    laboratory_authorization: dict | None = None,
    laboratory_experimental: bool = False,
):
    from processamento.limpeza_baloes import patch_degrade_experimento as base
    if isinstance(selections, dict):
        selections = [selections]
    if not isinstance(selections, list) or not selections:
        raise ValueError("Selecione pelo menos uma região.")
    original_selections = selections
    original = cv2.imread(str(source))
    if original is None:
        raise RuntimeError("Imagem inválida.")
    H, W = original.shape[:2]
    boxes=[]
    for s in selections:
        x,y,w,h=[int(round(float(s[k]))) for k in ("x","y","width","height")]
        if x<0 or y<0 or w<=0 or h<=0 or x+w>W or y+h>H:
            raise ValueError("ROI inválida.")
        boxes.append((x,y,w,h))
    started=time.perf_counter()
    target.mkdir(parents=True,exist_ok=True)
    t=time.perf_counter(); clean,mask=base._run_cleaner(source,target); cleaner=time.perf_counter()-t
    lab_approval = laboratory_authorization is not None
    if approved_check_rois and lab_approval:
        raise ValueError("Use uma única origem de autorização Degradê.")
    raw_clean=cv2.imread(str(clean)) if approved_check_rois or lab_approval else None
    raw_mask=cv2.imread(str(mask),cv2.IMREAD_GRAYSCALE) if approved_check_rois or lab_approval else None
    if (approved_check_rois or lab_approval) and (raw_clean is None or raw_mask is None):
        raise RuntimeError("Clean/mask candidatos ausentes para autorização especial.")
    if laboratory_experimental or lab_approval:
        raw_mask_path = target/"cleaner"/"source_mask_raw.png"
        raw_mask_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(mask, raw_mask_path)
    raw_mask_sha256 = None
    if lab_approval:
        from central_v2.backend.orchestration.textoff_special.artifacts import sha256
        raw_mask_sha256 = sha256(mask)
    t=time.perf_counter(); base._authorize_balloon(source,clean,mask,target); auth_seconds=time.perf_counter()-t
    special_components=[]
    if approved_check_rois or lab_approval:
        from processamento.limpeza_baloes.textoff_special_approval import apply_approved_rois
        approved_labels = None
        if lab_approval:
            from central_v2.backend.orchestration.textoff_special.artifacts import sha256
            from central_v2.backend.orchestration.textoff_special.lab_degrade_authorization import revalidate_worker
            auth = laboratory_authorization
            report_path = target/"balloon_authorization.json"
            source_hash = sha256(source)
            approved_labels = revalidate_worker(
                auth, source_hash, original_selections, report_path, raw_mask_sha256)
        special_components=apply_approved_rois(
            original,clean,mask,raw_clean,raw_mask,target/"balloon_authorization.json",boxes,
            approved_component_labels=approved_labels)
        if lab_approval and {item["component"] for item in special_components} != approved_labels:
            raise ValueError("PROPOSTA_OBSOLETA: componente confirmado não intersecta a ROI.")
    clean_img=cv2.imread(str(clean)); authorized=cv2.imread(str(mask),cv2.IMREAD_GRAYSCALE)
    if clean_img is None or authorized is None:
        raise RuntimeError("Clean/mask autorizados ausentes.")
    n,labels,stats,_=cv2.connectedComponentsWithStats((authorized>0).astype(np.uint8),connectivity=8)
    restricted=np.zeros_like(authorized); before=[]; selected=[]
    for label in range(1,n):
        area=int(stats[label,cv2.CC_STAT_AREA])
        if area<100: continue
        x=int(stats[label,cv2.CC_STAT_LEFT]); y=int(stats[label,cv2.CC_STAT_TOP])
        w=int(stats[label,cv2.CC_STAT_WIDTH]); h=int(stats[label,cv2.CC_STAT_HEIGHT])
        component=labels==label; hits=[]
        for idx,(rx,ry,rw,rh) in enumerate(boxes,1):
            if np.any(component[ry:ry+rh,rx:rx+rw]):
                hits.append(idx)
        item={"label":label,"bbox":[x,y,w,h],"area":area,"roi_hits":hits}
        before.append(item)
        if hits:
            restricted[component]=255
            selected.append(item)
    if not selected:
        raise RuntimeError("Nenhum componente autorizado intersecta as seleções.")
    restricted_mask=target/"roi_authorized_mask.png"
    if not cv2.imwrite(str(restricted_mask),restricted):
        raise RuntimeError("Falha ao salvar máscara ROI.")
    rebuilt=original.copy(); keep=restricted>0; rebuilt[keep]=clean_img[keep]
    if not cv2.imwrite(str(clean),rebuilt):
        raise RuntimeError("Falha ao reconstruir clean ROI.")
    t=time.perf_counter(); surface=target/"roi_surface_allowed.png"; base._surface(clean,restricted_mask,surface); surface_s=time.perf_counter()-t
    t=time.perf_counter(); processed,filled=base._local_heal(clean,restricted_mask,surface,target); heal=time.perf_counter()-t
    result=target/"01_local_heal.png"
    if not result.is_file():
        raise RuntimeError("ROI Degradê não gerou resultado.")

    # O algoritmo protegido continua trabalhando sobre o SOURCE.
    # O arquivo promovível, porém, parte da base oficial usada pela proposta
    # e recebe somente as alterações efetivamente produzidas pelo ROI.
    technical_result=cv2.imread(str(result))
    if technical_result is None:
        raise RuntimeError("Resultado técnico do ROI Degradê inválido.")
    if technical_result.shape != original.shape:
        raise RuntimeError("Resultado técnico do ROI Degradê possui dimensões incompatíveis.")

    changed_from_source=np.any(technical_result != original,axis=2)
    effective_changed_pixels=int(np.count_nonzero(changed_from_source))

    composition_mode="source_without_official_base"
    outside_effective_change_pixels=0

    if base_snapshot is not None:
        official_base=cv2.imread(str(base_snapshot))
        if official_base is None:
            raise RuntimeError("Snapshot da base oficial do ROI Degradê inválido.")
        if official_base.shape != original.shape:
            raise RuntimeError("Snapshot da base oficial possui dimensões incompatíveis.")

        composed=official_base.copy()
        composed[changed_from_source]=technical_result[changed_from_source]

        outside_effective_change_pixels=int(np.count_nonzero(
            np.any(composed != official_base,axis=2) & ~changed_from_source
        ))
        if outside_effective_change_pixels != 0:
            raise RuntimeError(
                "ROI Degradê alterou pixels fora da composição efetiva autorizada."
            )

        promotion_result=target/"promotion_result.png"
        if not cv2.imwrite(str(promotion_result),composed):
            raise RuntimeError("Falha ao salvar composição segura do ROI Degradê.")

        composition_mode="effective_changes_over_official_base"
    else:
        promotion_result=result

    meta={"algorithm":ALGORITHM,"proof_phase":False,"promotion_allowed":True,
          "selection_count":len(boxes),"selections":[list(b) for b in boxes],
          "authorization_rule":("explicit_laboratory_components_intersecting_roi"
                                if lab_approval else
                                "whole_existing_authorized_components_intersecting_roi"),
          "authorized_pixels_before_roi":int(np.count_nonzero(authorized)),
          "authorized_pixels_after_roi":int(np.count_nonzero(restricted)),
          "components_before_count":len(before),"components_selected_count":len(selected),
          "components_selected_by_roi":selected,"processed_components":int(processed),
          "approved_check_rois":approved_check_rois,
          "laboratory_authorization":({
              "proposal_run_id": laboratory_authorization["proposal_run_id"],
              "components": special_components,
              "source": "explicit_laboratory_confirmation",
          } if lab_approval else None),
          "special_components":special_components,
          "pixels_filled":int(filled),
          "composition_mode":composition_mode,
          "effective_changed_pixels":effective_changed_pixels,
          "outside_effective_change_pixels":outside_effective_change_pixels,
          "base_snapshot_used":base_snapshot is not None,
          "preview_result":result.name,
          "promotion_result":promotion_result.name,
          "timing_seconds":{"cleaner":round(cleaner,3),"balloon_authorization":round(auth_seconds,3),
                            "surface_gate":round(surface_s,3),"local_heal":round(heal,3),
                            "total":round(time.perf_counter()-started,3)},
          "protected_patch_modified":False}
    if laboratory_experimental or lab_approval:
        meta.setdefault("artifacts", {})["raw_cleaner_mask"] = "cleaner/source_mask_raw.png"
    (target/"roi_report.json").write_text(json.dumps(meta,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    return result,meta
