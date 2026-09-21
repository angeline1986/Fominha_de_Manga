from __future__ import annotations
import json, shutil, subprocess, sys
from pathlib import Path

import cv2
import numpy as np

from processamento.limpeza_baloes import patch_degrade_experimento as base

OUT = base.ROOT / "reports/experimentos/patch_balao_estilizado"
MIN_AREA = 100
GRAPHIC_DETAIL_PROTECTION_V1 = True
GRAPHIC_SAT_MIN = 70
GRAPHIC_LOCAL_SAT_DELTA = 24
GRAPHIC_LOCAL_VALUE_DELTA = 18
GRAPHIC_MAX_COMPONENT_AREA = 1800
GRAPHIC_DILATE = 1

def _components(mask_path: Path):
    raw=cv2.imread(str(mask_path),cv2.IMREAD_GRAYSCALE)
    if raw is None: raise RuntimeError("Falha ao abrir máscara Cleaner.")
    mask=(raw>0).astype(np.uint8)
    n,labels,stats,_=cv2.connectedComponentsWithStats(mask,connectivity=8)
    comps=[]
    for label in range(1,n):
        area=int(stats[label,cv2.CC_STAT_AREA])
        if area<MIN_AREA: continue
        x=int(stats[label,cv2.CC_STAT_LEFT]); y=int(stats[label,cv2.CC_STAT_TOP])
        w=int(stats[label,cv2.CC_STAT_WIDTH]); h=int(stats[label,cv2.CC_STAT_HEIGHT])
        comps.append((label,x,y,w,h,area))
    return mask,labels,comps

def _make_overlay(page: Path, labels, comps, dest: Path):
    img=cv2.imread(str(page))
    if img is None: raise RuntimeError("Falha ao abrir imagem original.")
    overlay=img.copy()
    for idx,(label,x,y,w,h,area) in enumerate(comps,1):
        cv2.rectangle(overlay,(x,y),(x+w-1,y+h-1),(0,0,255),2)
        cv2.putText(overlay,str(idx),(x,max(22,y-6)),cv2.FONT_HERSHEY_SIMPLEX,.8,(0,0,255),2,cv2.LINE_AA)
    if not cv2.imwrite(str(dest),overlay): raise RuntimeError("Falha ao salvar overlay.")
    return dest

def _select_components(comps):
    print("\nComponentes encontrados pelo Cleaner:")
    for idx,(_,x,y,w,h,area) in enumerate(comps,1):
        print(f"[{idx}] bbox=({x},{y},{w},{h}) area={area}")
    print("\nAutorize SOMENTE componentes que visualmente estão dentro de balões.")
    print("Texto externo/SFX deve ficar sem seleção. Enter ou 0 = preservar tudo.")
    raw=input("Componentes autorizados (ex.: 2,3) › ").strip()
    if not raw or raw=="0": return []
    out=[]
    for token in raw.split(","):
        token=token.strip()
        if not token: continue
        n=int(token)
        if not 1<=n<=len(comps): raise ValueError(f"Componente fora da lista: {n}")
        if n not in out: out.append(n)
    return out

def _authorized_mask(mask_path: Path, page: Path, target: Path):
    mask,labels,comps=_components(mask_path)
    overlay=_make_overlay(page,labels,comps,target/"00_componentes.png")
    print(f"\nOverlay: {overlay}")
    if sys.platform=="darwin": subprocess.run(["open",str(overlay)],check=False)
    selected=_select_components(comps)
    authorized=np.zeros(mask.shape,np.uint8)
    decisions=[]
    for idx,(label,x,y,w,h,area) in enumerate(comps,1):
        ok=idx in selected
        if ok: authorized[labels==label]=255
        decisions.append({"index":idx,"label":label,"bbox":[x,y,w,h],"area":area,
                          "decision":"authorize" if ok else "preserve"})
    out=target/"01_authorized_mask.png"
    if not cv2.imwrite(str(out),authorized): raise RuntimeError("Falha ao salvar máscara autorizada.")
    return out,decisions

def _protect_graphic_details(page: Path, auth_mask: Path, target: Path):
    original=cv2.imread(str(page)); raw=cv2.imread(str(auth_mask),cv2.IMREAD_GRAYSCALE)
    if original is None or raw is None: raise RuntimeError("Falha ao abrir original/máscara.")
    mask=raw>0
    hsv=cv2.cvtColor(original,cv2.COLOR_BGR2HSV)
    sat=hsv[:,:,1].astype(np.int16); val=hsv[:,:,2].astype(np.int16)
    sat_med=cv2.medianBlur(hsv[:,:,1],31).astype(np.int16)
    val_med=cv2.medianBlur(hsv[:,:,2],31).astype(np.int16)
    candidate=mask & (sat>=GRAPHIC_SAT_MIN) & (((sat-sat_med)>=GRAPHIC_LOCAL_SAT_DELTA)|((val_med-val)>=GRAPHIC_LOCAL_VALUE_DELTA))
    n,labels,stats,_=cv2.connectedComponentsWithStats(candidate.astype(np.uint8),8)
    protected=np.zeros(mask.shape,np.uint8); details=[]
    for label in range(1,n):
        area=int(stats[label,cv2.CC_STAT_AREA])
        if area<3 or area>GRAPHIC_MAX_COMPONENT_AREA: continue
        x=int(stats[label,cv2.CC_STAT_LEFT]); y=int(stats[label,cv2.CC_STAT_TOP])
        w=int(stats[label,cv2.CC_STAT_WIDTH]); h=int(stats[label,cv2.CC_STAT_HEIGHT])
        protected[labels==label]=255
        details.append({"bbox":[x,y,w,h],"area":area})
    if GRAPHIC_DILATE and np.any(protected):
        k=cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(3,3))
        protected=cv2.dilate(protected,k,iterations=GRAPHIC_DILATE); protected[~mask]=0
    effective=(mask & (protected==0)).astype(np.uint8)*255
    cv2.imwrite(str(target/"02_graphic_protected.png"),protected)
    cv2.imwrite(str(target/"03_effective_mask.png"),effective)
    return target/"03_effective_mask.png",details,int(np.count_nonzero(protected))

def _rebuild_clean_from_original(page: Path, cleaner_clean: Path, auth_mask: Path):
    original=cv2.imread(str(page)); clean=cv2.imread(str(cleaner_clean))
    mask=cv2.imread(str(auth_mask),cv2.IMREAD_GRAYSCALE)
    if original is None or clean is None or mask is None: raise RuntimeError("Entrada inválida.")
    if original.shape!=clean.shape or original.shape[:2]!=mask.shape: raise RuntimeError("Dimensões incompatíveis.")
    keep=mask>0
    result=original.copy()
    result[keep]=clean[keep]
    if not cv2.imwrite(str(cleaner_clean),result): raise RuntimeError("Falha ao reconstruir clean autorizado.")
    # Local Heal deve receber somente a máscara autorizada.
    return cleaner_clean

def _run(chapter,page):
    target=OUT/chapter.name/page.stem
    if target.exists(): shutil.rmtree(target)
    target.mkdir(parents=True)
    print(f"\n--- {chapter.name} · {page.name} ---")
    try:
        clean,raw_mask=base._run_cleaner(page,target)
        print("2/5 Autorização assistida de componentes...")
        auth_mask,decisions=_authorized_mask(raw_mask,page,target)
        _rebuild_clean_from_original(page,clean,auth_mask)
        print("3/5 Proteção de detalhes gráficos...")
        effective_mask,graphic_details,protected_pixels=_protect_graphic_details(page,auth_mask,target)
        print(f"    detalhes protegidos: {len(graphic_details)} · pixels protegidos: {protected_pixels}")
        _rebuild_clean_from_original(page,clean,effective_mask)
        print("4/5 Surface Gate...")
        surface=target/"04_surface_allowed.png"; base._surface(clean,effective_mask,surface)
        print("5/5 Local Heal (parâmetros congelados do Patch Degradê)...")
        components,filled=base._local_heal(clean,effective_mask,surface,target)
        meta={"source":str(page),"mode":"styled_balloon_assisted_graphic_protection_v1",
              "authorized_mask":str(auth_mask),"effective_mask":str(effective_mask),
              "graphic_protection":{"algorithm":"local_hsv_detail_v1","details":graphic_details,"protected_pixels":protected_pixels},
              "decisions":decisions,
              "parameters":{"patch":"9x9","search_radius":70,"search_step":2,
                            "min_context":12,"source_valid":0.92},
              "components":components,"pixels_filled":filled}
        (target/"run.json").write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding="utf-8")
        print(f"Concluído: {target/'01_local_heal.png'}")
        if sys.platform=="darwin": subprocess.run(["open",str(target/"01_local_heal.png")],check=False)
    except Exception as exc:
        print(f"ERRO: {exc}")

def run_styled_balloon_experiment():
    IMG=base.IMG
    chapters=sorted([p for p in IMG.iterdir() if p.is_dir() and any((p/n).is_file() for n in base.ALLOWED)],key=base._key)
    print("\nPATCH BALÃO ESTILIZADO · EXPERIMENTO ASSISTIDO")
    print("Regra: somente componentes explicitamente autorizados seguem para o Local Heal.")
    print("\nSelecione o capítulo:\n")
    for i,ch in enumerate(chapters,1): print(f"[{i}] {ch.name}")
    print("[0] Voltar")
    n=base._choose("\nCapítulo › ",len(chapters))
    if n==0:return
    chapter=chapters[n-1]; pages=[chapter/n for n in base.ALLOWED if (chapter/n).is_file()]
    print(f"\n{chapter.name}\n")
    for i,p in enumerate(pages,1):print(f"[{i}] {p.name}")
    while True:
        raw=input("\nPáginas (ex.: 3; 0=Voltar) › ").strip()
        if raw=="0":return
        try:selected=base._parse(raw,len(pages));break
        except ValueError as exc:print(exc)
    for i in selected:_run(chapter,pages[i-1])
    print(f"\nResultados: {OUT/chapter.name}")
    print("Nenhum arquivo oficial foi alterado.")
