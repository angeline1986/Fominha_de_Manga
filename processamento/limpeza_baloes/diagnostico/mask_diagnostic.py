"""Diagnóstico isolado da máscara do Cleaner V2 por página interna de um MERGE.
Não promove, não sobrescreve e não altera artefatos oficiais.
"""
from __future__ import annotations
from pathlib import Path
import argparse, json, os, shutil, subprocess, tempfile, time

ROOT=Path(__file__).resolve().parents[3]
CLEANER=ROOT/"processamento"/"limpeza_baloes"/"cleaner_v2"

def _components(cv2,np,mask,y0,y1):
    band=(mask[y0:y1]>0).astype(np.uint8)
    n,_,stats,_=cv2.connectedComponentsWithStats(band,8)
    out=[]
    for i in range(1,n):
        x=int(stats[i,cv2.CC_STAT_LEFT]); y=int(stats[i,cv2.CC_STAT_TOP])
        w=int(stats[i,cv2.CC_STAT_WIDTH]); h=int(stats[i,cv2.CC_STAT_HEIGHT])
        area=int(stats[i,cv2.CC_STAT_AREA])
        if area>=8:
            out.append({"x":x,"y_local":y,"y_global":y+y0,"w":w,"h":h,"area":area})
    return sorted(out,key=lambda x:x["area"],reverse=True)

def _ranges(cv2,manga,chapter,merged_name,merged_h):
    import re
    m=re.fullmatch(r"page-(\d+)-(\d+)\.[^.]+",merged_name,re.I)
    if not m: raise ValueError("Nome MERGE não segue page-NNN-NNN.ext.")
    start,end=map(int,m.groups())
    pages=[]; total=0
    for num in range(start,end+1):
        matches=sorted((manga/"IMG"/chapter).glob(f"page-{num:03d}.*"))
        if not matches: raise FileNotFoundError(f"IMG interna page-{num:03d} ausente.")
        im=cv2.imread(str(matches[0]))
        if im is None: raise RuntimeError(f"Falha ao ler {matches[0]}")
        h=im.shape[0]; pages.append((num,h)); total+=h
    out=[]; acc=0
    for num,h in pages:
        y0=round(acc/total*merged_h); acc+=h; y1=round(acc/total*merged_h)
        out.append({"page":f"{num:03d}","y1":y0,"y2":y1})
    return out

def run(manga,chapter,source_file,internal_page):
    import cv2, numpy as np
    from huggingface_hub import hf_hub_download
    from ultralytics import YOLO
    from processamento.limpeza_baloes.cleaner_v2.launcher import build_command
    from processamento.limpeza_baloes.cleaner_v2.balloon_authorization import (
        MODEL_REPO,MODEL_FILE,MODEL_REVISION,CONF,IOU
    )

    manga=Path(manga).expanduser().resolve()
    source=(manga/"FLUXO_SECUNDARIO"/"02_MERGE"/chapter/source_file).resolve()
    if not source.is_file(): raise FileNotFoundError(source)

    stamp=time.strftime("%Y%m%d_%H%M%S")
    report_dir=ROOT/"reports"/"diagnosticos"/f"textoff-mask-{chapter.replace(' ','_')}-{internal_page}-{stamp}"
    report_dir.mkdir(parents=True,exist_ok=False)
    work=Path(tempfile.mkdtemp(prefix=".textoff-mask-diag-",dir=str(report_dir)))
    try:
        inp=work/"input"; out=work/"output"; inp.mkdir(); out.mkdir()
        os.symlink(source,inp/source.name)
        progress=work/"progress.json"
        cmd=build_command(inp,out,offline=True,progress_file=progress)
        print(f"[MaskDiag] Cleaner START source={source.name}",flush=True)
        p=subprocess.run(cmd,cwd=CLEANER,check=False)
        if p.returncode: raise RuntimeError(f"Cleaner encerrou com código {p.returncode}")

        masks=sorted(out.glob(f"{source.stem}_mask.*"))
        if len(masks)!=1: raise RuntimeError(f"Esperava 1 máscara bruta; encontrei {len(masks)}")
        raw=cv2.imread(str(masks[0]),cv2.IMREAD_GRAYSCALE)
        original=cv2.imread(str(source))
        if raw is None or original is None: raise RuntimeError("Falha ao ler fonte/máscara bruta.")

        print("[MaskDiag] Balloon gate START",flush=True)
        model_path=hf_hub_download(repo_id=MODEL_REPO,filename=MODEL_FILE,revision=MODEL_REVISION)
        model=YOLO(model_path)
        result=model.predict(source=original,conf=CONF,iou=IOU,verbose=False)[0]
        balloon=np.zeros(raw.shape,dtype=np.uint8); balloons=0
        if result.masks is not None:
            for poly in result.masks.xy:
                pts=np.asarray(poly,dtype=np.int32)
                if len(pts)>=3: cv2.fillPoly(balloon,[pts],255); balloons+=1
        effective=cv2.bitwise_and(raw,balloon)

        ranges=_ranges(cv2,manga,chapter,source.name,raw.shape[0])
        target=next((r for r in ranges if r["page"]==str(internal_page).zfill(3)),None)
        if not target: raise ValueError(f"Página interna {internal_page} não pertence a {source.name}")
        y0,y1=int(target["y1"]),int(target["y2"])
        raw_px=int(np.count_nonzero(raw[y0:y1]))
        balloon_px=int(np.count_nonzero(balloon[y0:y1]))
        eff_px=int(np.count_nonzero(effective[y0:y1]))
        rejected_px=int(np.count_nonzero((raw[y0:y1]>0)&(balloon[y0:y1]==0)))

        # Overlay diagnóstico: verde=autorizado; vermelho=rejeitado pelo gate.
        page_crop=original[y0:y1].copy()
        raw_components=_components(cv2,np,raw,y0,y1)
        effective_components=_components(cv2,np,effective,y0,y1)
        def _key(c):
            return (c["x"],c["y_local"],c["w"],c["h"],c["area"])
        effective_keys={_key(c) for c in effective_components}
        overlay_rows=[]
        for idx,c in enumerate(raw_components,1):
            authorized=_key(c) in effective_keys
            status="AUTORIZADA" if authorized else "REJEITADA PELO BALLOON GATE"
            color=(0,190,0) if authorized else (0,0,255)
            x=int(c["x"]); yy=int(c["y_local"]); w=int(c["w"]); h=int(c["h"])
            cv2.rectangle(page_crop,(x,yy),(x+w-1,yy+h-1),color,3)
            label=f"{chr(64+idx)} - {status}"
            ty=max(24,yy-8)
            cv2.putText(page_crop,label,(max(4,x),ty),cv2.FONT_HERSHEY_SIMPLEX,0.62,(255,255,255),4,cv2.LINE_AA)
            cv2.putText(page_crop,label,(max(4,x),ty),cv2.FONT_HERSHEY_SIMPLEX,0.62,color,2,cv2.LINE_AA)
            overlay_rows.append({"label":chr(64+idx),"status":status,**c})
        overlay_path=report_dir/"mask-overlay.png"
        if not cv2.imwrite(str(overlay_path),page_crop):
            raise RuntimeError("Falha ao gravar overlay diagnóstico.")

        report={
          "schema":"textoff_mask_diagnostic_v1",
          "read_only":True,
          "source":str(source),"chapter":chapter,"source_file":source.name,
          "internal_page":str(internal_page).zfill(3),"internal_range":target,
          "model":{"repo":MODEL_REPO,"file":MODEL_FILE,"revision":MODEL_REVISION,"conf":CONF,"iou":IOU},
          "balloons_detected_merged":balloons,
          "internal_page_pixels":{
            "cleaner_raw_mask":raw_px,
            "balloon_mask":balloon_px,
            "effective_authorized_mask":eff_px,
            "cleaner_pixels_rejected_by_balloon_gate":rejected_px,
            "authorized_percent_of_cleaner":round(eff_px/raw_px*100,4) if raw_px else 0.0
          },
          "raw_components":raw_components,
          "effective_components":effective_components,
          "overlay":"mask-overlay.png",
          "overlay_components":overlay_rows
        }
        rp=report_dir/"mask-diagnostic.json"
        rp.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print("[MaskDiag] DONE")
        print(f"[MaskDiag] raw={raw_px} effective={eff_px} rejected={rejected_px} authorized={report['internal_page_pixels']['authorized_percent_of_cleaner']}%")
        print(f"[MaskDiag] report={rp}")
        print(f"[MaskDiag] overlay={overlay_path}")
        return rp
    finally:
        shutil.rmtree(work,ignore_errors=True)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--manga",required=True)
    ap.add_argument("--chapter",required=True)
    ap.add_argument("--source-file",required=True)
    ap.add_argument("--internal-page",required=True)
    a=ap.parse_args()
    run(a.manga,a.chapter,a.source_file,a.internal_page)

if __name__=="__main__": main()
