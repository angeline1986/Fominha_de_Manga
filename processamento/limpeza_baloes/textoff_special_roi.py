from pathlib import Path
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
):
    from processamento.limpeza_baloes import patch_degrade_experimento as base
    if isinstance(selections, dict):
        selections = [selections]
    if not isinstance(selections, list) or not selections:
        raise ValueError("Selecione pelo menos uma região.")
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
    t=time.perf_counter(); base._authorize_balloon(source,clean,mask,target); auth=time.perf_counter()-t
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
          "authorization_rule":"whole_existing_authorized_components_intersecting_roi",
          "authorized_pixels_before_roi":int(np.count_nonzero(authorized)),
          "authorized_pixels_after_roi":int(np.count_nonzero(restricted)),
          "components_before_count":len(before),"components_selected_count":len(selected),
          "components_selected_by_roi":selected,"processed_components":int(processed),
          "pixels_filled":int(filled),
          "composition_mode":composition_mode,
          "effective_changed_pixels":effective_changed_pixels,
          "outside_effective_change_pixels":outside_effective_change_pixels,
          "base_snapshot_used":base_snapshot is not None,
          "preview_result":result.name,
          "promotion_result":promotion_result.name,
          "timing_seconds":{"cleaner":round(cleaner,3),"balloon_authorization":round(auth,3),
                            "surface_gate":round(surface_s,3),"local_heal":round(heal,3),
                            "total":round(time.perf_counter()-started,3)},
          "protected_patch_modified":False}
    (target/"roi_report.json").write_text(json.dumps(meta,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    return result,meta
