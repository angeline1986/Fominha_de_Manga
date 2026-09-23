from pathlib import Path
import json, time
import cv2
import numpy as np

ALGORITHM="textoff_gradiente_suave_v1"
EXPANSION_RATIO=0.35
MIN_EXPANSION=12
BAND=12
SMOOTH_KERNEL=41

def reconstruct(source_path: Path, output_path: Path, bbox, report_path: Path|None=None):
    started=time.perf_counter()
    source=cv2.imread(str(source_path))
    if source is None: raise RuntimeError("Imagem não carregada.")
    x,y,w,h=map(int,bbox)
    ih,iw=source.shape[:2]
    if x<0 or y<0 or w<=0 or h<=0 or x+w>iw or y+h>ih: raise ValueError("Seleção inválida.")
    expand=max(MIN_EXPANSION,round(h*EXPANSION_RATIO))
    x1=max(BAND,x-expand); y1=max(BAND,y-expand)
    x2=min(iw-BAND,x+w+expand); y2=min(ih-BAND,y+h+expand)
    rw,rh=x2-x1,y2-y1
    if rw<3 or rh<1: raise ValueError("Região expandida insuficiente.")
    lab=cv2.cvtColor(source,cv2.COLOR_BGR2LAB).astype(np.float32)
    top=lab[y1-BAND:y1,x1:x2]; bottom=lab[y2:y2+BAND,x1:x2]
    if top.shape[0]!=BAND or bottom.shape[0]!=BAND: raise ValueError("Contexto insuficiente.")
    tp=np.median(top,axis=0); bp=np.median(bottom,axis=0)
    kernel=max(3,min(SMOOTH_KERNEL,rw if rw%2 else rw-1))
    tp=cv2.GaussianBlur(tp.reshape(1,rw,3),(kernel,1),0).reshape(rw,3)
    bp=cv2.GaussianBlur(bp.reshape(1,rw,3),(kernel,1),0).reshape(rw,3)
    surface=np.empty((rh,rw,3),dtype=np.float32)
    for row in range(rh):
        t=row/max(rh-1,1)
        surface[row]=tp*(1.0-t)+bp*t
    rebuilt=cv2.cvtColor(np.clip(surface,0,255).astype(np.uint8),cv2.COLOR_LAB2BGR)
    result=source.copy()
    result[y1:y2,x1:x2]=rebuilt
    outside=np.ones((ih,iw),dtype=bool); outside[y1:y2,x1:x2]=False
    outside_changed=int(np.count_nonzero(np.any(result!=source,axis=2)&outside))
    if outside_changed: raise RuntimeError("Alteração fora da região de escrita.")
    output_path.parent.mkdir(parents=True,exist_ok=True)
    if not cv2.imwrite(str(output_path),result): raise RuntimeError("Falha ao gravar resultado.")
    meta={"algorithm":ALGORITHM,"selection_bbox_pixels":[x,y,w,h],
          "expansion_ratio":EXPANSION_RATIO,"minimum_expansion_pixels":MIN_EXPANSION,
          "expansion_pixels":expand,"write_bbox_pixels":[x1,y1,x2,y2],
          "context_band_pixels":BAND,"smooth_kernel":kernel,
          "outside_write_changed_pixels":outside_changed,
          "elapsed_ms":round((time.perf_counter()-started)*1000,3)}
    if report_path:
        report_path.write_text(json.dumps(meta,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    return meta
