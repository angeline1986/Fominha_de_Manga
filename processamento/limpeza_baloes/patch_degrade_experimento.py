#!/usr/bin/env python3
"""Patch Degradê experimental, autossuficiente por página.

Pipeline reproduzido:
IMG original -> Panel Cleaner (workspace temporário) -> surface gate LAB/conectividade
-> Local Heal congelado -> saída experimental.
Não altera IMG nem artefatos oficiais.
"""
from __future__ import annotations
import time
import json, re, shutil, subprocess, sys
from pathlib import Path

from processamento.limpeza_baloes.cleaner_v2.balloon_authorization import apply_balloon_authorization

ROOT=Path(__file__).resolve().parents[2]
MANGA=ROOT/"download"/"mangago_downloader"/"output"/"mangago"/"Candy YumYum (Yaoi)"
IMG=MANGA/"IMG"
OUT=ROOT/"reports"/"experimentos"/"patch_degrade"
ALLOWED=("page-051.png","page-052.png","page-053.png")
CLEANER_DIR=ROOT/"processamento"/"limpeza_baloes"/"cleaner_v2"
CLEANER_PY=CLEANER_DIR/".venv"/"bin"/"python"
CLEANER_MAIN=CLEANER_DIR/"main.py"
PROFILE=CLEANER_DIR/"preserve-colors.ini"

PATCH_RADIUS=4
SEARCH_RADIUS=70
SEARCH_STEP=2
MIN_CONTEXT=12
SOURCE_VALID=0.92

def _key(p): return [int(x) if x.isdigit() else x.lower() for x in re.split(r"(\d+)",p.name)]

def _choose(prompt,total):
    while True:
        raw=input(prompt).strip()
        if raw=="0": return 0
        try:n=int(raw)
        except ValueError: print("Opção inválida."); continue
        if 1<=n<=total:return n
        print("Opção inválida.")

def _parse(raw,total):
    out=[]
    for token in raw.split(","):
        token=token.strip()
        if not token:continue
        try:n=int(token)
        except ValueError:raise ValueError(f"Seleção inválida: {token}")
        if not 1<=n<=total:raise ValueError(f"Página fora da lista: {n}")
        if n not in out:out.append(n)
    if not out:raise ValueError("Nenhuma página selecionada.")
    return out

def _run_cleaner(page,target):
    input_dir=target/"cleaner_input"; output_dir=target/"cleaner"
    if input_dir.exists():shutil.rmtree(input_dir)
    if output_dir.exists():shutil.rmtree(output_dir)
    input_dir.mkdir(parents=True); output_dir.mkdir(parents=True)
    shutil.copy2(page,input_dir/page.name)
    cmd=[str(CLEANER_PY),str(CLEANER_MAIN),"-i",str(input_dir),"-o",str(output_dir),
         "--profile",str(PROFILE),"--timeout","900"]
    print("1/4 Cleaner: gerando clean + mask...")
    proc=subprocess.run(cmd,cwd=str(CLEANER_DIR),check=False)
    if proc.returncode:raise RuntimeError(f"Cleaner encerrou com código {proc.returncode}")
    clean=output_dir/f"{page.stem}_clean.png"
    mask=output_dir/f"{page.stem}_mask.png"
    if not clean.is_file() or not mask.is_file():
        found=", ".join(p.name for p in sorted(output_dir.iterdir()))
        raise RuntimeError(f"Cleaner não gerou clean/mask esperados. Saída: {found or '(vazia)'}")
    return clean,mask

def _authorize_balloon(page, clean, mask, target):
    report=target/"balloon_authorization.json"
    # A função estável modifica SOMENTE os clean/mask do workspace experimental:
    # effective = cleaner_mask & balloon_mask e reconstrói clean a partir do original.
    data=apply_balloon_authorization([page], clean.parent, report)
    authorized=int(data.get("authorized_mask_pixels",0))
    raw=int(data.get("cleaner_mask_pixels",0))
    pct=float(data.get("authorized_percent",0.0))
    print(f"    máscara Cleaner={raw} px · autorizada={authorized} px · {pct:.2f}%")
    return report

def _surface(clean_path,mask_path,dest):
    import cv2, numpy as np
    clean=cv2.imread(str(clean_path)); raw=cv2.imread(str(mask_path),cv2.IMREAD_GRAYSCALE)
    if clean is None or raw is None:raise RuntimeError("Falha ao abrir clean/mask.")
    mask=(raw>0).astype(np.uint8); lab=cv2.cvtColor(clean,cv2.COLOR_BGR2LAB)
    n,labels,stats,_=cv2.connectedComponentsWithStats(mask,connectivity=8)
    surface=np.zeros(mask.shape,np.uint8)
    for label in range(1,n):
        x=int(stats[label,cv2.CC_STAT_LEFT]); y=int(stats[label,cv2.CC_STAT_TOP])
        w=int(stats[label,cv2.CC_STAT_WIDTH]); h=int(stats[label,cv2.CC_STAT_HEIGHT])
        area=int(stats[label,cv2.CC_STAT_AREA])
        if area<100:continue
        component=labels==label; comp8=component.astype(np.uint8)*255
        outer=cv2.dilate(comp8,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(41,41)))>0
        inner=cv2.dilate(comp8,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(9,9)))>0
        samples=lab[outer & ~inner & (mask==0)]
        if len(samples)<50:continue
        ref=np.median(samples,axis=0)
        L=lab[:,:,0].astype(np.float32); A=lab[:,:,1].astype(np.float32); B=lab[:,:,2].astype(np.float32)
        compatible=(np.abs(L-ref[0])<48)&(np.abs(A-ref[1])<18)&(np.abs(B-ref[2])<18)&(mask==0)
        mx=max(100,w); my=max(100,h)
        x0=max(0,x-mx); y0=max(0,y-my); x1=min(clean.shape[1],x+w+mx); y1=min(clean.shape[0],y+h+my)
        local=cv2.morphologyEx(compatible[y0:y1,x0:x1].astype(np.uint8),cv2.MORPH_OPEN,np.ones((3,3),np.uint8))
        sn,slabels,_,_=cv2.connectedComponentsWithStats(local,connectivity=8)
        local_component=component[y0:y1,x0:x1]
        near=cv2.dilate(local_component.astype(np.uint8),cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(17,17)))>0
        allowed=np.zeros_like(local)
        for sid in range(1,sn):
            region=slabels==sid
            if np.any(region & near):allowed[region]=1
        surface[y0:y1,x0:x1]=np.maximum(surface[y0:y1,x0:x1],allowed*255)
    if not cv2.imwrite(str(dest),surface):raise RuntimeError("Falha ao salvar surface_allowed.")
    return surface

def _local_heal(clean_path,mask_path,surface_path,out_dir):
    import cv2, numpy as np
    clean=cv2.imread(str(clean_path)); mask_raw=cv2.imread(str(mask_path),cv2.IMREAD_GRAYSCALE)
    surface_raw=cv2.imread(str(surface_path),cv2.IMREAD_GRAYSCALE)
    if clean is None or mask_raw is None or surface_raw is None:raise RuntimeError("clean/mask/surface inválido.")
    mask=mask_raw>0; surface=surface_raw>0; H,W=mask.shape
    result=clean.copy()
    n,labels,stats,_=cv2.connectedComponentsWithStats(mask.astype(np.uint8),connectivity=8)
    debug=clean.copy(); processed=filled_total=0
    def bounds(cx,cy,r):return cx-r,cy-r,cx+r+1,cy+r+1
    for label in range(1,n):
        x=int(stats[label,cv2.CC_STAT_LEFT]); y=int(stats[label,cv2.CC_STAT_TOP])
        w=int(stats[label,cv2.CC_STAT_WIDTH]); h=int(stats[label,cv2.CC_STAT_HEIGHT])
        area=int(stats[label,cv2.CC_STAT_AREA])
        if area<100:continue
        component=labels==label
        near=cv2.dilate(component.astype(np.uint8),cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(SEARCH_RADIUS*2+1,SEARCH_RADIUS*2+1)))>0
        allowed=surface & near & ~mask; remaining=component.copy()
        iteration=component_filled=0
        print(f"  Componente {label}: bbox=({x},{y},{w},{h}) area={area}")
        while np.any(remaining):
            iteration+=1
            eroded=cv2.erode(remaining.astype(np.uint8),np.ones((3,3),np.uint8),iterations=1)>0
            fy,fx=np.where(remaining & ~eroded)
            if len(fx)==0:break
            filled_round=0
            for cy,cx in zip(fy[::2],fx[::2]):
                tx0,ty0,tx1,ty1=bounds(cx,cy,PATCH_RADIUS)
                if tx0<0 or ty0<0 or tx1>W or ty1>H:continue
                target=result[ty0:ty1,tx0:tx1]
                target_remaining=remaining[ty0:ty1,tx0:tx1]; known=~target_remaining
                if np.count_nonzero(known)<MIN_CONTEXT:continue
                best_score=best_patch=best_xy=None
                sy0=max(PATCH_RADIUS,cy-SEARCH_RADIUS); sy1=min(H-PATCH_RADIUS,cy+SEARCH_RADIUS+1)
                sx0=max(PATCH_RADIUS,cx-SEARCH_RADIUS); sx1=min(W-PATCH_RADIUS,cx+SEARCH_RADIUS+1)
                for sy in range(sy0,sy1,SEARCH_STEP):
                    for sx in range(sx0,sx1,SEARCH_STEP):
                        px0,py0,px1,py1=bounds(sx,sy,PATCH_RADIUS)
                        if np.mean(allowed[py0:py1,px0:px1])<SOURCE_VALID:continue
                        source=clean[py0:py1,px0:px1]
                        a=target[known].astype(np.float32); b=source[known].astype(np.float32)
                        if len(a)==0:continue
                        visual=np.mean((a-b)**2); distance=np.hypot(float(sx-cx),float(sy-cy))
                        score=visual+(distance*distance*0.12)
                        if best_score is None or score<best_score:
                            best_score=score; best_patch=source; best_xy=(sx,sy)
                if best_patch is None:continue
                local=remaining[ty0:ty1,tx0:tx1]; view=result[ty0:ty1,tx0:tx1]
                count=int(np.count_nonzero(local))
                view[local]=best_patch[local]; result[ty0:ty1,tx0:tx1]=view
                rem_view=remaining[ty0:ty1,tx0:tx1]; rem_view[local]=False; remaining[ty0:ty1,tx0:tx1]=rem_view
                component_filled+=count; filled_round+=count
                if best_xy:cv2.line(debug,(cx,cy),best_xy,(0,255,0),1)
            if filled_round==0 or iteration>500:break
        print(f"    preenchidos={component_filled} restantes={np.count_nonzero(remaining)} iterações={iteration}")
        processed+=1; filled_total+=component_filled
    cv2.imwrite(str(out_dir/"01_local_heal.png"),result)
    # Mantém também as duas saídas históricas.
    mask8=mask.astype(np.uint8)*255
    inner=cv2.erode(mask8,np.ones((3,3),np.uint8),iterations=1)
    boundary=((mask8>0)&(inner==0)).astype(np.uint8)
    alpha=np.clip(cv2.GaussianBlur(boundary.astype(np.float32),(5,5),0),0,1)[...,None]
    mixed=result.astype(np.float32)*0.65+clean.astype(np.float32)*0.35
    blended=result.astype(np.float32)*(1-alpha)+mixed*alpha
    cv2.imwrite(str(out_dir/"02_local_heal_blended.png"),np.clip(blended,0,255).astype(np.uint8))
    cv2.imwrite(str(out_dir/"03_source_map.png"),debug)
    return processed,filled_total

def _run(chapter,page):
    target=OUT/chapter.name/page.stem
    if target.exists():shutil.rmtree(target)
    target.mkdir(parents=True)
    print(f"\n--- {chapter.name} · {page.name} ---")
    try:
        total_t0=time.perf_counter()
        step_t0=time.perf_counter()
        clean,mask=_run_cleaner(page,target)
        cleaner_s=time.perf_counter()-step_t0
        print(f"    ⏱ Cleaner: {cleaner_s:.2f}s")
        print("2/4 Balloon Authorization: Cleaner mask ∩ Balloon mask...")
        step_t0=time.perf_counter()
        auth_report=_authorize_balloon(page,clean,mask,target)
        balloon_s=time.perf_counter()-step_t0
        print(f"    ⏱ Balloon Authorization: {balloon_s:.2f}s")
        print("3/4 Surface gate: LAB + conectividade...")
        step_t0=time.perf_counter()
        surface_path=target/"01_surface_allowed.png"; _surface(clean,mask,surface_path)
        surface_s=time.perf_counter()-step_t0
        print(f"    ⏱ Surface Gate: {surface_s:.2f}s")
        print("4/4 Local Heal: 9x9 · radius 70 · step 2 · source >=92%...")
        step_t0=time.perf_counter()
        components,filled=_local_heal(clean,mask,surface_path,target)
        local_heal_s=time.perf_counter()-step_t0
        total_s=time.perf_counter()-total_t0
        print(f"    ⏱ Local Heal: {local_heal_s:.2f}s")
        print(f"    ⏱ TEMPO TOTAL: {total_s:.2f}s")
        timing={"cleaner":round(cleaner_s,3),"balloon_authorization":round(balloon_s,3),"surface_gate":round(surface_s,3),"local_heal":round(local_heal_s,3),"total":round(total_s,3)}
        meta={"source":str(page),"clean":str(clean),"mask":str(mask),"balloon_authorization":str(auth_report),"surface":str(surface_path),"timing_seconds":timing,
              "parameters":{"patch":"9x9","search_radius":70,"search_step":2,"min_context":12,"source_valid":0.92},"components":components,"pixels_filled":filled}
        (target/"run.json").write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding="utf-8")
        print(f"Concluído: {target/'01_local_heal.png'}")
        if sys.platform=="darwin":subprocess.run(["open",str(target/"01_local_heal.png")],check=False)
    except Exception as exc:
        print(f"ERRO: {exc}")

def run_patch_degrade_experiment():
    if not IMG.is_dir():print(f"IMG não encontrada: {IMG}");return
    if not CLEANER_PY.is_file():print(f"Cleaner V2 .venv não encontrado: {CLEANER_PY}");return
    chapters=sorted([p for p in IMG.iterdir() if p.is_dir() and any((p/n).is_file() for n in ALLOWED)],key=_key)
    print("\nPATCH DEGRADÊ · EXPERIMENTO ISOLADO")
    print("Obra: Candy YumYum (Yaoi)")
    print("Pipeline: IMG → Cleaner temporário → Balloon Authorization → Surface Gate → Local Heal")
    print("\nSelecione o capítulo:\n")
    for i,ch in enumerate(chapters,1):print(f"[{i}] {ch.name}")
    print("[0] Voltar")
    n=_choose("\nCapítulo › ",len(chapters))
    if n==0:return
    chapter=chapters[n-1]; pages=[chapter/n for n in ALLOWED if (chapter/n).is_file()]
    print(f"\n{chapter.name}\n")
    for i,p in enumerate(pages,1):print(f"[{i}] {p.name}")
    while True:
        raw=input("\nPáginas (ex.: 1 ou 1,2,3; 0=Voltar) › ").strip()
        if raw=="0":return
        try:selected=_parse(raw,len(pages));break
        except ValueError as exc:print(exc)
    for i in selected:_run(chapter,pages[i-1])
    print(f"\nResultados: {OUT/chapter.name}")
    print("Nenhum arquivo oficial foi alterado.")
