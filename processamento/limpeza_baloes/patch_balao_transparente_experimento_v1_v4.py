from __future__ import annotations
import json, re, shutil, subprocess, sys, time
from pathlib import Path
import cv2
import numpy as np
from processamento.limpeza_baloes import patch_degrade_experimento as base

OUT=base.ROOT/"reports/experimentos/patch_balao_transparente"
MIN_AREA=100
SEARCH_RADIUS=base.SEARCH_RADIUS

def _key(p):
    return [int(x) if x.isdigit() else x.lower() for x in re.split(r"(\d+)",p.name)]

def _pages(chapter):
    exts={".png",".jpg",".jpeg",".webp",".bmp"}
    return sorted([p for p in chapter.iterdir() if p.is_file() and p.suffix.lower() in exts],key=_key)

def _components(mask_path):
    raw=cv2.imread(str(mask_path),cv2.IMREAD_GRAYSCALE)
    if raw is None: raise RuntimeError("Falha ao abrir máscara Cleaner.")
    mask=(raw>0).astype(np.uint8)
    n,labels,stats,_=cv2.connectedComponentsWithStats(mask,8)
    comps=[]
    for label in range(1,n):
        area=int(stats[label,cv2.CC_STAT_AREA])
        if area<MIN_AREA: continue
        x=int(stats[label,cv2.CC_STAT_LEFT]); y=int(stats[label,cv2.CC_STAT_TOP])
        w=int(stats[label,cv2.CC_STAT_WIDTH]); h=int(stats[label,cv2.CC_STAT_HEIGHT])
        comps.append((label,x,y,w,h,area))
    return mask,labels,comps

def _overlay(page,comps,dest):
    img=cv2.imread(str(page))
    if img is None: raise RuntimeError("Falha ao abrir original.")
    out=img.copy()
    for idx,(_,x,y,w,h,area) in enumerate(comps,1):
        cv2.rectangle(out,(x,y),(x+w-1,y+h-1),(0,0,255),2)
        cv2.putText(out,str(idx),(x,max(24,y-7)),cv2.FONT_HERSHEY_SIMPLEX,.8,(0,0,255),2,cv2.LINE_AA)
    if not cv2.imwrite(str(dest),out): raise RuntimeError("Falha ao salvar overlay.")
    return dest

def _select(comps):
    print("\nComponentes Cleaner encontrados:")
    for idx,(_,x,y,w,h,area) in enumerate(comps,1):
        print(f"[{idx}] bbox=({x},{y},{w},{h}) area={area}")
    print("\nSelecione SOMENTE texto dentro de balões semitransparentes.")
    while True:
        raw=input("Componentes (ex.: 2,3; 0=cancelar) › ").strip()
        if raw=="0": return []
        try: return base._parse(raw,len(comps))
        except ValueError as exc: print(exc)

def _authorized_mask(mask,labels,comps,selected,dest):
    auth=np.zeros(mask.shape,np.uint8); decisions=[]
    for idx,(label,x,y,w,h,area) in enumerate(comps,1):
        ok=idx in selected
        if ok: auth[labels==label]=255
        decisions.append({"index":idx,"bbox":[x,y,w,h],"area":area,"decision":"transparent_heal" if ok else "preserve"})
    if not cv2.imwrite(str(dest),auth): raise RuntimeError("Falha ao salvar máscara autorizada.")
    return decisions

def _source_allowed(auth_path,raw_path,dest):
    auth=cv2.imread(str(auth_path),cv2.IMREAD_GRAYSCALE)
    raw=cv2.imread(str(raw_path),cv2.IMREAD_GRAYSCALE)
    if auth is None or raw is None: raise RuntimeError("Máscara inválida.")
    selected=auth>0; all_text=raw>0
    k=cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(SEARCH_RADIUS*2+1,SEARCH_RADIUS*2+1))
    near=cv2.dilate(selected.astype(np.uint8),k,iterations=1)>0
    allowed=(near & ~all_text).astype(np.uint8)*255
    if not cv2.imwrite(str(dest),allowed): raise RuntimeError("Falha ao salvar source_allowed.")
    return int(np.count_nonzero(allowed))

def _structural_inpaint(page, auth_path, target):
    original=cv2.imread(str(page))
    mask=cv2.imread(str(auth_path),cv2.IMREAD_GRAYSCALE)
    if original is None or mask is None: raise RuntimeError("Entrada inválida para inpainting estrutural.")
    mask=(mask>0).astype(np.uint8)*255
    telea=cv2.inpaint(original,mask,3.0,cv2.INPAINT_TELEA)
    ns=cv2.inpaint(original,mask,3.0,cv2.INPAINT_NS)
    telea_path=target/"03_inpaint_telea_r3.png"
    ns_path=target/"04_inpaint_ns_r3.png"
    cv2.imwrite(str(telea_path),telea); cv2.imwrite(str(ns_path),ns)
    divider=np.full((original.shape[0],6,3),255,np.uint8)
    comparison=np.hstack([original,divider,telea,divider,ns])
    compare_path=target/"05_comparativo_estrutural.png"
    cv2.imwrite(str(compare_path),comparison)
    return telea_path,ns_path,compare_path

def _alpha_diagnostic(page, auth_path, target):
    original=cv2.imread(str(page))
    mask=cv2.imread(str(auth_path),cv2.IMREAD_GRAYSCALE)
    if original is None or mask is None: raise RuntimeError("Entrada inválida.")
    text=mask>0
    text8=text.astype(np.uint8)*255
    closed=cv2.morphologyEx(text8,cv2.MORPH_CLOSE,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(31,31)),iterations=2)
    bubble=cv2.dilate(closed,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(81,81)),iterations=1)>0
    bubble8=bubble.astype(np.uint8)*255
    bg=cv2.inpaint(original,bubble8,7.0,cv2.INPAINT_TELEA).astype(np.float32)
    obs=original.astype(np.float32)
    denom=255.0-bg
    valid=np.abs(denom)>8.0
    ach=np.zeros_like(obs,dtype=np.float32)
    ach[valid]=(obs[valid]-bg[valid])/denom[valid]
    alpha=np.clip(np.median(ach,axis=2),0.0,0.95)
    known=bubble & ~text
    alpha[~known]=0.0
    # OpenCV 4.13: medianBlur ksize=9 exige CV_8U neste ambiente.
    alpha_u8=np.clip(alpha*255.0,0,255).astype(np.uint8)
    alpha=cv2.medianBlur(alpha_u8,9).astype(np.float32)/255.0
    au8=np.clip(alpha*255,0,255).astype(np.uint8)
    holes=(bubble & ~known).astype(np.uint8)*255
    af=cv2.inpaint(au8,holes,5.0,cv2.INPAINT_TELEA).astype(np.float32)/255.0
    af[~bubble]=0.0
    rec=af[...,None]*255.0+(1.0-af[...,None])*bg
    rec=np.clip(rec,0,255).astype(np.uint8)
    err=np.mean(np.abs(rec.astype(np.float32)-obs),axis=2)
    ek=err[known]
    vis=original.copy()
    contours,_=cv2.findContours(bubble8,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(vis,contours,-1,(0,0,255),2)
    cv2.imwrite(str(target/"02_bubble_region.png"),vis)
    cv2.imwrite(str(target/"03_estimated_alpha.png"),np.clip(af*255,0,255).astype(np.uint8))
    cv2.imwrite(str(target/"04_estimated_background.png"),np.clip(bg,0,255).astype(np.uint8))
    cv2.imwrite(str(target/"05_recomposed_check.png"),rec)
    heat=np.clip(err*5,0,255).astype(np.uint8)
    heat=cv2.applyColorMap(heat,cv2.COLORMAP_JET); heat[~known]=0
    cv2.imwrite(str(target/"06_recomposition_error.png"),heat)
    return {"bubble_pixels":int(np.count_nonzero(bubble)),
            "known_pixels":int(np.count_nonzero(known)),
            "alpha_median":float(np.median(alpha[known])) if np.any(known) else None,
            "alpha_p10":float(np.percentile(alpha[known],10)) if np.any(known) else None,
            "alpha_p90":float(np.percentile(alpha[known],90)) if np.any(known) else None,
            "recomposition_mae":float(np.mean(ek)) if ek.size else None,
            "recomposition_p95":float(np.percentile(ek,95)) if ek.size else None}

def _alpha_hybrid_v4(page, auth_path, target):
    original=cv2.imread(str(page))
    mask=cv2.imread(str(auth_path),cv2.IMREAD_GRAYSCALE)
    if original is None or mask is None: raise RuntimeError("Entrada inválida para V4.")
    text=mask>0
    ys,xs=np.where(text)
    x0,x1=int(xs.min()),int(xs.max()); y0,y1=int(ys.min()),int(ys.max())
    h,w=original.shape[:2]
    mx=max(28,int((x1-x0+1)*0.18)); my=max(22,int((y1-y0+1)*0.28))
    rx0=max(0,x0-mx); rx1=min(w,x1+mx+1); ry0=max(0,y0-my); ry1=min(h,y1+my+1)
    roi=np.zeros((h,w),np.uint8); roi[ry0:ry1,rx0:rx1]=255
    known=(roi>0) & ~text
    gray=cv2.cvtColor(original,cv2.COLOR_BGR2GRAY).astype(np.float32)
    mean=cv2.GaussianBlur(gray,(0,0),5.0)
    dev=np.abs(gray-mean)
    vals=dev[known]
    contrast=float(np.percentile(vals,75)) if vals.size else 0.0
    alpha=float(np.clip(0.72-contrast/90.0,0.18,0.72))
    obs=original.astype(np.float32)
    recovered=np.clip((obs-alpha*255.0)/max(1e-3,1.0-alpha),0,255).astype(np.uint8)
    recovered[roi==0]=original[roi==0]
    text8=text.astype(np.uint8)*255
    bt=cv2.inpaint(recovered,text8,3.0,cv2.INPAINT_TELEA)
    bn=cv2.inpaint(recovered,text8,3.0,cv2.INPAINT_NS)
    def recompose(bg):
        out=original.copy()
        comp=np.clip(alpha*255.0+(1.0-alpha)*bg.astype(np.float32),0,255).astype(np.uint8)
        out[text]=comp[text]
        return out
    ot=recompose(bt); on=recompose(bn)
    cv2.imwrite(str(target/"02_v4_work_region.png"),roi)
    cv2.imwrite(str(target/"03_v4_recovered_background.png"),recovered)
    cv2.imwrite(str(target/"04_v4_telea_recomposed.png"),ot)
    cv2.imwrite(str(target/"05_v4_ns_recomposed.png"),on)
    divider=np.full((h,6,3),255,np.uint8)
    cv2.imwrite(str(target/"06_v4_comparison.png"),np.hstack([original,divider,ot,divider,on]))
    return {"alpha_estimate":alpha,"local_contrast_p75":contrast,
            "work_bbox":[rx0,ry0,rx1-rx0,ry1-ry0],
            "text_pixels":int(np.count_nonzero(text)),
            "method":"contrast_alpha_then_inpaint_background_then_recompose"}

def _run(chapter,page):
    target=OUT/chapter.name/page.stem
    if target.exists(): shutil.rmtree(target)
    target.mkdir(parents=True)
    print(f"\n--- {chapter.name} · {page.name} ---")
    t0=time.perf_counter()
    try:
        _,raw_mask=base._run_cleaner(page,target)
        mask,labels,comps=_components(raw_mask)
        if not comps:
            print("Cleaner não gerou componentes elegíveis."); return
        overlay=_overlay(page,comps,target/"00_componentes.png")
        print(f"Overlay: {overlay}")
        if sys.platform=="darwin": subprocess.run(["open",str(overlay)],check=False)
        selected=_select(comps)
        if not selected:
            print("Cancelado. Nenhum arquivo oficial foi alterado."); return
        auth=target/"01_transparent_mask.png"
        decisions=_authorized_mask(mask,labels,comps,selected,auth)
        print("\nHíbrido Alpha V4")
        print("Fluxo: alpha por contraste -> desfazer camada -> reconstruir fundo -> recompor.")
        metrics=_alpha_hybrid_v4(page,auth,target)
        meta={"source":str(page),"mode":"transparent_balloon_alpha_hybrid_v4",
              "decisions":decisions,"metrics":metrics,
              "note":"experimental only; no official artifact changed",
              "elapsed_seconds":round(time.perf_counter()-t0,3)}
        (target/"run.json").write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding="utf-8")
        print(f"alpha estimado={metrics['alpha_estimate']:.3f}")
        print(f"contraste local p75={metrics['local_contrast_p75']:.2f}")
        print(f"\nComparativo: {target/'06_v4_comparison.png'}")
        print("Ordem: ORIGINAL | V4 TELEA | V4 NAVIER-STOKES")
        print("Nenhum arquivo oficial foi alterado.")
        if sys.platform=="darwin":
            subprocess.run(["open",str(target/"06_v4_comparison.png")],check=False)
    except Exception as exc:
        print(f"ERRO: {type(exc).__name__}: {exc}")

def run_transparent_balloon_experiment():
    IMG=base.IMG
    chapters=sorted([p for p in IMG.iterdir() if p.is_dir() and _pages(p)],key=_key)
    print("\nPATCH BALÃO TRANSPARENTE · EXPERIMENTO V4")
    print("Híbrido alpha + reconstrução do fundo; seleção manual para calibração.\n")
    for i,ch in enumerate(chapters,1): print(f"[{i}] {ch.name}")
    print("[0] Voltar")
    n=base._choose("\nCapítulo › ",len(chapters))
    if n==0:return
    chapter=chapters[n-1]
    pages=_pages(chapter)
    if chapter.name=="Ch. 3":
        test_names={"page-036.png","page-037.png","page-040.png","page-084.png"}
        pages=[p for p in pages if p.name in test_names]
    if not pages:
        print("Nenhuma página de teste disponível para este capítulo.")
        return
    print(f"\n{chapter.name}\n")
    for i,p in enumerate(pages,1): print(f"[{i}] {p.name}")
    while True:
        raw=input("\nPáginas (ex.: 37 ou 37,40; 0=Voltar) › ").strip()
        if raw=="0":return
        try:selected=base._parse(raw,len(pages));break
        except ValueError as exc:print(exc)
    for i in selected:_run(chapter,pages[i-1])
    print(f"\nResultados: {OUT/chapter.name}")
