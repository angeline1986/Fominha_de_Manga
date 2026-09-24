from pathlib import Path
import json, time
import cv2
import numpy as np
ALGORITHM="textoff_special_roi_styled_v1"

def run_styled_roi(source: Path,target: Path,selections,base_snapshot: Path|None=None):
    from processamento.limpeza_baloes import patch_balao_estilizado_experimento as styled
    from processamento.limpeza_baloes import patch_degrade_experimento as base
    if isinstance(selections,dict): selections=[selections]
    if not isinstance(selections,list) or not selections: raise ValueError("Selecione pelo menos uma região.")
    original=cv2.imread(str(source))
    if original is None: raise RuntimeError("Imagem inválida.")
    H,W=original.shape[:2]; boxes=[]
    for s in selections:
        x,y,w,h=[int(round(float(s[k]))) for k in ("x","y","width","height")]
        if x<0 or y<0 or w<=0 or h<=0 or x+w>W or y+h>H: raise ValueError("ROI inválida.")
        boxes.append((x,y,w,h))
    started=time.perf_counter(); target.mkdir(parents=True,exist_ok=True)
    t=time.perf_counter(); clean,raw_mask=base._run_cleaner(source,target); cleaner=time.perf_counter()-t
    t=time.perf_counter(); authorized_path,decisions=styled._authorized_mask(raw_mask,source,target); classifier=time.perf_counter()-t
    clean_img=cv2.imread(str(clean)); authorized=cv2.imread(str(authorized_path),cv2.IMREAD_GRAYSCALE)
    if clean_img is None or authorized is None: raise RuntimeError("Clean/máscara autorizada ausentes.")
    n,labels,stats,_=cv2.connectedComponentsWithStats((authorized>0).astype(np.uint8),connectivity=8)
    restricted=np.zeros_like(authorized); before=[]; selected=[]
    for label in range(1,n):
        area=int(stats[label,cv2.CC_STAT_AREA])
        if area<styled.MIN_AREA: continue
        x=int(stats[label,cv2.CC_STAT_LEFT]); y=int(stats[label,cv2.CC_STAT_TOP]); w=int(stats[label,cv2.CC_STAT_WIDTH]); h=int(stats[label,cv2.CC_STAT_HEIGHT])
        component=labels==label; hits=[]
        for idx,(rx,ry,rw,rh) in enumerate(boxes,1):
            if np.any(component[ry:ry+rh,rx:rx+rw]): hits.append(idx)
        item={"label":label,"bbox":[x,y,w,h],"area":area,"roi_hits":hits}; before.append(item)
        if hits: restricted[component]=255; selected.append(item)
    if not selected: raise RuntimeError("Nenhum componente autorizado pelo Estilizado intersecta as seleções.")
    # Diagnóstico visual exclusivo do adapter ROI.
    # Não interfere na máscara, classificação ou processamento protegido.
    overlay=original.copy()
    for idx,(rx,ry,rw,rh) in enumerate(boxes,1):
        hit=any(idx in item["roi_hits"] for item in selected)
        color=(0,200,0) if hit else (0,165,255)
        cv2.rectangle(overlay,(rx,ry),(rx+rw-1,ry+rh-1),color,3)
        cv2.putText(overlay,f"ROI {idx}",(rx,max(22,ry-8)),cv2.FONT_HERSHEY_SIMPLEX,0.65,color,2,cv2.LINE_AA)
    for item in selected:
        x,y,w,h=item["bbox"]
        cv2.rectangle(overlay,(x,y),(x+w-1,y+h-1),(255,0,255),2)
        cv2.putText(overlay,"C"+str(item["label"]),(x,max(22,y-8)),cv2.FONT_HERSHEY_SIMPLEX,0.65,(255,0,255),2,cv2.LINE_AA)
    overlay_path=target/"00_componentes_roi.png"
    if not cv2.imwrite(str(overlay_path),overlay): raise RuntimeError("Falha ao salvar overlay diagnóstico do ROI.")

    restricted_path=target/"roi_authorized_mask.png"
    if not cv2.imwrite(str(restricted_path),restricted): raise RuntimeError("Falha ao salvar máscara ROI.")
    rebuilt=original.copy(); keep=restricted>0; rebuilt[keep]=clean_img[keep]
    if not cv2.imwrite(str(clean),rebuilt): raise RuntimeError("Falha ao reconstruir clean ROI.")
    t=time.perf_counter(); surface=target/"roi_surface_allowed.png"; base._surface(clean,restricted_path,surface); surface_s=time.perf_counter()-t
    t=time.perf_counter(); processed,filled=base._local_heal(clean,restricted_path,surface,target); heal=time.perf_counter()-t
    result=target/"01_local_heal.png"
    if not result.is_file(): raise RuntimeError("ROI Estilizado não gerou resultado.")
    technical=cv2.imread(str(result))
    if technical is None or technical.shape!=original.shape: raise RuntimeError("Resultado técnico inválido.")
    changed=np.any(technical!=original,axis=2); effective=int(np.count_nonzero(changed)); outside=int(np.count_nonzero(changed & ~(restricted>0)))
    mode="source_without_official_base"
    promotion_result=result
    if base_snapshot is not None:
        official=cv2.imread(str(base_snapshot))
        if official is None or official.shape!=original.shape: raise RuntimeError("Snapshot oficial inválido.")
        composed=official.copy(); composed[changed]=technical[changed]
        promotion_result=target/"promotion_result.png"
        if not cv2.imwrite(str(promotion_result),composed): raise RuntimeError("Falha ao salvar composição segura.")
        mode="effective_changes_over_official_base"
    meta={"algorithm":ALGORITHM,"proof_phase":True,"promotion_allowed":False,"selection_count":len(boxes),"selections":[list(b) for b in boxes],"authorization_rule":"styled_authorized_components_intersecting_roi","authorized_pixels_before_roi":int(np.count_nonzero(authorized)),"authorized_pixels_after_roi":int(np.count_nonzero(restricted)),"components_before_count":len(before),"components_selected_count":len(selected),"components_selected_by_roi":selected,"classifier_decisions":decisions,"processed_components":int(processed),"pixels_filled":int(filled),"composition_mode":mode,"effective_changed_pixels":effective,"technical_changed_outside_authorized_pixels":outside,"base_snapshot_used":base_snapshot is not None,"preview_result":result.name,"promotion_result":promotion_result.name,"timing_seconds":{"cleaner":round(cleaner,3),"styled_classifier":round(classifier,3),"surface_gate":round(surface_s,3),"local_heal":round(heal,3),"total":round(time.perf_counter()-started,3)},"protected_patch_modified":False}
    (target/"roi_report.json").write_text(json.dumps(meta,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    return result,meta
