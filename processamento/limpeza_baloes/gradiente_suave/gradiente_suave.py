from pathlib import Path
import json, time
import cv2
import numpy as np

ALGORITHM="textoff_gradiente_suave_v1"
EXPANSION_RATIO=0.35
MIN_EXPANSION=12
BAND=12
SMOOTH_KERNEL=41

def _region_from_source(source_lab, image_shape, bbox):
    x,y,w,h=map(int,bbox); ih,iw=image_shape[:2]
    if x<0 or y<0 or w<=0 or h<=0 or x+w>iw or y+h>ih: raise ValueError("Seleção inválida.")
    expand=max(MIN_EXPANSION,round(h*EXPANSION_RATIO))
    x1=max(BAND,x-expand); y1=max(BAND,y-expand); x2=min(iw-BAND,x+w+expand); y2=min(ih-BAND,y+h+expand)
    rw,rh=x2-x1,y2-y1
    if rw<3 or rh<1: raise ValueError("Região expandida insuficiente.")
    top=source_lab[y1-BAND:y1,x1:x2]; bottom=source_lab[y2:y2+BAND,x1:x2]
    if top.shape[0]!=BAND or bottom.shape[0]!=BAND: raise ValueError("Contexto insuficiente.")
    tp=np.median(top,axis=0); bp=np.median(bottom,axis=0); kernel=max(3,min(SMOOTH_KERNEL,rw if rw%2 else rw-1))
    tp=cv2.GaussianBlur(tp.reshape(1,rw,3),(kernel,1),0).reshape(rw,3); bp=cv2.GaussianBlur(bp.reshape(1,rw,3),(kernel,1),0).reshape(rw,3)
    surface=np.empty((rh,rw,3),dtype=np.float32)
    for row in range(rh):
        t=row/max(rh-1,1); surface[row]=tp*(1.0-t)+bp*t
    return cv2.cvtColor(np.clip(surface,0,255).astype(np.uint8),cv2.COLOR_LAB2BGR),{"selection_bbox_pixels":[x,y,w,h],"expansion_pixels":expand,"write_bbox_pixels":[x1,y1,x2,y2],"smooth_kernel":kernel}

def _overlap(a,b):
    ax1,ay1,ax2,ay2=a; bx1,by1,bx2,by2=b
    return max(ax1,bx1)<min(ax2,bx2) and max(ay1,by1)<min(ay2,by2)

def reconstruct_many(source_path: Path, output_path: Path, bboxes, report_path: Path|None=None):
    started=time.perf_counter(); source=cv2.imread(str(source_path))
    if source is None: raise RuntimeError("Imagem não carregada.")
    bboxes=list(bboxes or [])
    if not bboxes: raise ValueError("Selecione pelo menos uma área.")
    lab=cv2.cvtColor(source,cv2.COLOR_BGR2LAB).astype(np.float32); prepared=[]
    for bbox in bboxes:
        rebuilt,meta=_region_from_source(lab,source.shape,bbox)
        for _,previous in prepared:
            if _overlap(meta["write_bbox_pixels"],previous["write_bbox_pixels"]): raise ValueError("As áreas expandidas do Gradiente Suave se sobrepõem. Ajuste ou remova uma das seleções.")
        prepared.append((rebuilt,meta))
    result=source.copy(); authorized=np.zeros(source.shape[:2],dtype=bool)
    for rebuilt,meta in prepared:
        x1,y1,x2,y2=meta["write_bbox_pixels"]; result[y1:y2,x1:x2]=rebuilt; authorized[y1:y2,x1:x2]=True
    outside=int(np.count_nonzero(np.any(result!=source,axis=2)&~authorized))
    if outside: raise RuntimeError("Alteração fora das regiões de escrita.")
    output_path.parent.mkdir(parents=True,exist_ok=True)
    if not cv2.imwrite(str(output_path),result): raise RuntimeError("Falha ao gravar resultado.")
    meta={"algorithm":ALGORITHM,"selection_count":len(prepared),"expansion_ratio":EXPANSION_RATIO,"minimum_expansion_pixels":MIN_EXPANSION,"context_band_pixels":BAND,"regions":[m for _,m in prepared],"outside_write_changed_pixels":outside,"elapsed_ms":round((time.perf_counter()-started)*1000,3)}
    if report_path: report_path.write_text(json.dumps(meta,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    return meta

def reconstruct(source_path: Path, output_path: Path, bbox, report_path: Path|None=None):
    meta=reconstruct_many(source_path,output_path,[bbox],report_path); region=meta["regions"][0]
    return {"algorithm":meta["algorithm"],**region,"expansion_ratio":meta["expansion_ratio"],"minimum_expansion_pixels":meta["minimum_expansion_pixels"],"context_band_pixels":meta["context_band_pixels"],"outside_write_changed_pixels":meta["outside_write_changed_pixels"],"elapsed_ms":meta["elapsed_ms"]}
