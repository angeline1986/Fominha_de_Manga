"""Patch Degradê v1 — Local Heal para Correção Assistida."""
from __future__ import annotations
import time
from datetime import datetime, timezone
import json, os, re, shutil, subprocess, tempfile, uuid
from pathlib import Path
from PIL import Image
from processamento.limpeza_baloes.textoff_level3 import _item_key,_normalize_stage,_validate_image_name,pending_for_chapter
from processamento.limpeza_baloes.textoff_level3_correction import CLEANER_VENV_PYTHON,ROOT,SCHEMA,STATUS,_chapter_name,_proposals_root,_sha256,_validate_current_pair

ALGORITHM="textoff_gradient_patch_v1"
PATCH_DEGRADE_DIAG_V3_2=True
PATCH_SIZE=9; PATCH_RADIUS=4; SEARCH_RADIUS=70; SEARCH_STEP=2; MIN_SOURCE_VALID=.92; MIN_CONTEXT=12

_PAGE_RANGE_RE=re.compile(r"^page-(\d+)-(\d+)\.(?:png|jpe?g|webp|bmp)$",re.I)

def internal_pages_for(source_file):
    m=_PAGE_RANGE_RE.fullmatch(str(source_file or "").strip())
    if not m: return []
    a,b=map(int,m.groups())
    if b<a or b-a>200: return []
    width=max(len(m.group(1)),len(m.group(2)),3)
    return [f"page-{n:0{width}d}" for n in range(a,b+1)]

def _selected_band_mask(manga,chapter,source_path,source_file,selected_pages):
    pages=internal_pages_for(source_file)
    selected=[str(x).strip() for x in (selected_pages or [])]
    if not pages: raise ValueError("Merged sem intervalo interno identificável.")
    if not selected: raise ValueError("Selecione pelo menos uma página interna.")
    invalid=[x for x in selected if x not in pages]
    if invalid: raise ValueError("Página interna inválida: "+", ".join(invalid))
    img_dir=(manga/"IMG"/str(chapter)).resolve()
    rows=[]; total=0
    for page in pages:
        candidates=[x for x in img_dir.glob(page+".*") if x.suffix.lower() in {".png",".jpg",".jpeg",".webp",".bmp"} and x.is_file()]
        if len(candidates)!=1: raise ValueError(f"Não foi possível resolver {page} unicamente em IMG/{chapter}.")
        src=candidates[0].resolve()
        if not src.is_relative_to(img_dir): raise ValueError("Página interna fora de IMG.")
        with Image.open(src) as im: w,h=im.size
        rows.append({"page":page,"file":src.name,"source_width":int(w),"source_height":int(h),"start":total,"end":total+int(h)})
        total+=int(h)
    with Image.open(source_path) as im: mw,mh=im.size
    if total<=0: raise ValueError("Altura interna inválida.")
    scale=float(mh)/float(total)
    return [{"page":r["page"],"source_file":r["file"],"source_height":r["source_height"],"source_width":r["source_width"],
             "x1":0,"y1":max(0,round(r["start"]*scale)),"x2":int(mw),"y2":min(int(mh),round(r["end"]*scale)),
             "scale_to_merged":scale} for r in rows if r["page"] in selected]

def _mask_for(clean_dir: Path, source_file: str, clean_file: str) -> Path:
    manifest_path = clean_dir / "clean-manifest.json"
    if not manifest_path.is_file():
        raise ValueError(f"Manifesto do Cleaner V2 não encontrado: {manifest_path}")
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    sources = [str(x) for x in (payload.get("source_artifacts") or [])]
    cleans = [str(x) for x in (payload.get("clean_artifacts") or [])]
    masks = [str(x) for x in (payload.get("mask_artifacts") or [])]
    if not (len(sources) == len(cleans) == len(masks)):
        raise ValueError("Manifesto do Cleaner V2 não possui mapeamento completo source/clean/mask.")
    clean_root = clean_dir.resolve()
    for src, clean, mask in zip(sources, cleans, masks):
        if src == source_file and clean == clean_file:
            mask_path = (clean_dir / mask).resolve()
            if not mask_path.is_relative_to(clean_root):
                raise ValueError("Máscara do Cleaner V2 aponta para fora do diretório permitido.")
            if not mask_path.is_file():
                raise ValueError(f"Máscara do Cleaner V2 não encontrada: {mask_path}")
            return mask_path
    raise ValueError(f"Máscara correspondente não localizada para source={source_file} clean={clean_file}.")


def generate_gradient_preview(manga,chapter,source_stage,source_file,clean_file,selected_pages):
    print(f"[PatchDegrade] START source={source_file} chapter={chapter} stage={source_stage} selected={selected_pages}",flush=True)
    chapter=_chapter_name(chapter); stage=_normalize_stage(source_stage)
    source_file=_validate_image_name(source_file,"Imagem original"); clean_file=_validate_image_name(clean_file,"Imagem limpa")
    item=pending_for_chapter(manga,chapter).get(_item_key(stage,source_file))
    if not item: raise ValueError("A página não está pendente de correção assistida.")
    if str(item.get("clean_file") or "")!=clean_file: raise ValueError("Resultado atual divergente da pendência.")
    source_path,clean_path=_validate_current_pair(manga,chapter,stage,source_file,clean_file)
    mask_path=_mask_for(clean_path.parent,source_file,clean_file)
    _t_ranges=time.monotonic()
    if stage=="ORIGINAL":
        with Image.open(source_path) as im:
            width,height=im.size
        internal_ranges=[{"page":Path(source_file).stem,"source_file":source_file,
                          "source_height":int(height),"source_width":int(width),
                          "x1":0,"y1":0,"x2":int(width),"y2":int(height),
                          "scale_to_merged":1.0}]
    else:
        internal_ranges=_selected_band_mask(manga,chapter,source_path,source_file,selected_pages)
    print(f"[PatchDegrade] RANGES elapsed={time.monotonic()-_t_ranges:.3f}s ranges={internal_ranges}",flush=True)
    with Image.open(source_path) as a,Image.open(clean_path) as b,Image.open(mask_path) as c:
        if a.size!=b.size or a.size!=c.size: raise RuntimeError("Fonte, clean e máscara possuem dimensões divergentes.")
    base_sha=_sha256(clean_path); source_sha=_sha256(source_path); mask_sha=_sha256(mask_path)
    pid=datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")+"_"+uuid.uuid4().hex[:8]
    root=_proposals_root(manga,chapter); root.mkdir(parents=True,exist_ok=True)
    final=root/pid; tmp=Path(tempfile.mkdtemp(prefix=".gradient-patch-",dir=str(root)))
    preview=tmp/"preview.png"; report=tmp/"worker-report.json"
    try:
        env=os.environ.copy(); env["PYTHONPATH"]=str(ROOT)+(os.pathsep+env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
        ranges_path=tmp/"internal-ranges.json"; ranges_path.write_text(json.dumps(internal_ranges,ensure_ascii=False),encoding="utf-8")
        cmd=[str(CLEANER_VENV_PYTHON),str(Path(__file__).resolve()),"--worker","--clean",str(clean_path),"--mask",str(mask_path),"--preview",str(preview),"--report",str(report),"--ranges",str(ranges_path)]
        print(f"[PatchDegrade] WORKER spawn cmd={cmd}",flush=True)
        _t_worker=time.monotonic()
        p=subprocess.run(cmd,cwd=str(ROOT),env=env,text=True,capture_output=True,check=False)
        print(f"[PatchDegrade] WORKER exit={p.returncode} elapsed={time.monotonic()-_t_worker:.3f}s",flush=True)
        if p.stdout: print("[PatchDegrade][worker-stdout]\n"+p.stdout.rstrip(),flush=True)
        if p.stderr: print("[PatchDegrade][worker-stderr]\n"+p.stderr.rstrip(),flush=True)
        if p.returncode: raise RuntimeError("Falha Patch Degradê: "+((p.stderr or p.stdout or "")[-1600:]))
        if not preview.is_file() or not report.is_file(): raise RuntimeError("Worker não produziu preview/report.")
        w=json.loads(report.read_text(encoding="utf-8"))
        if _sha256(clean_path)!=base_sha or _sha256(source_path)!=source_sha or _sha256(mask_path)!=mask_sha: raise RuntimeError("Artefato oficial mudou durante a proposta.")
        manifest={"schema":SCHEMA,"proposal_id":pid,"chapter":chapter,"source_stage":stage,"source_file":source_file,"clean_file":clean_file,
          "origin":"GRADIENT_PATCH","algorithm":ALGORITHM,"status":STATUS,"created_at":datetime.now(timezone.utc).isoformat(timespec="seconds"),
          "base_sha256":base_sha,"source_sha256":source_sha,"mask_sha256":mask_sha,"preview_file":"preview.png",
          "selected_internal_pages":[r["page"] for r in internal_ranges],"internal_ranges_pixels":internal_ranges,
          "parameters":{"patch_size":9,"search_radius":70,"search_step":2,"min_source_valid":.92,"fill_strategy":"boundary_to_center","surface_gate":"lab_connected"},
          "coverage":{k:w.get(k) for k in ("components","mask_pixels","filled_pixels","remaining_pixels","filled_percent")},
          "safety":{"official_image_modified":False,"source_image_modified":False,"composition_limited_to_mask":True,"promotion_requires_explicit_approval":True}}
        report.unlink(missing_ok=True); (tmp/"proposal.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); os.replace(tmp,final)
        pct=float(w.get("filled_percent") or 0); rem=int(w.get("remaining_pixels") or 0)
        return {"status":STATUS,"proposal_id":pid,"chapter":chapter,"source_stage":stage,"source_file":source_file,"clean_file":clean_file,"preview_file":"preview.png","algorithm":ALGORITHM,"coverage":manifest["coverage"],"message":f"Patch Degradê gerado · {pct:.1f}% preenchido"+(f" · {rem} px restantes." if rem else ".")+" A imagem oficial permanece inalterada."}
    except Exception:
        shutil.rmtree(tmp,ignore_errors=True); raise

def generate_gradient_preview_job(manga,chs,payload):
    if len(chs)!=1: raise ValueError("Patch Degradê processa uma página por vez.")
    ch=chs[0]
    if str(payload.get("chapter") or ch.name).strip()!=str(ch.name): raise ValueError("Capítulo divergente.")
    return generate_gradient_preview(manga,ch.name,payload.get("source_stage"),payload.get("source_file"),payload.get("clean_file"),payload.get("selected_pages") or [])

def _worker(clean_path,mask_path,preview_path,report_path,ranges_path):
    _worker_t0=time.monotonic()
    print(f"[PatchDegradeWorker] START clean={clean_path.name} mask={mask_path.name}",flush=True)
    import cv2, numpy as np
    clean=cv2.imread(str(clean_path)); raw=cv2.imread(str(mask_path),cv2.IMREAD_GRAYSCALE)
    if clean is None or raw is None: raise RuntimeError("Não foi possível abrir clean/mask.")
    mask=raw>0
    ranges=json.loads(ranges_path.read_text(encoding="utf-8"))
    selected=np.zeros_like(mask,dtype=bool)
    for r in ranges: selected[int(r["y1"]):int(r["y2"]),int(r["x1"]):int(r["x2"])]=True
    raw_pixels=int(np.count_nonzero(mask))
    band_pixels=int(np.count_nonzero(selected))
    mask &= selected
    selected_pixels=int(np.count_nonzero(mask))
    print(f"[PatchDegradeWorker] MASK raw={raw_pixels} band={band_pixels} selected={selected_pixels}",flush=True)
    if not np.any(mask): raise ValueError("Seleção interna sem pixels na máscara do Cleaner.")
    H,W=mask.shape; lab=cv2.cvtColor(clean,cv2.COLOR_BGR2LAB); result=clean.copy()
    n,labels,stats,_=cv2.connectedComponentsWithStats(mask.astype(np.uint8),8)
    print(f"[PatchDegradeWorker] COMPONENTS total={max(0,n-1)}",flush=True)
    processed=filled_total=remaining_total=0
    for label in range(1,n):
        _comp_t0=time.monotonic()
        _comp_last=_comp_t0
        area=int(stats[label,cv2.CC_STAT_AREA])
        x=int(stats[label,cv2.CC_STAT_LEFT]); y=int(stats[label,cv2.CC_STAT_TOP]); w=int(stats[label,cv2.CC_STAT_WIDTH]); h=int(stats[label,cv2.CC_STAT_HEIGHT])
        print(f"[PatchDegradeWorker] COMPONENT {label}/{n-1} bbox=({x},{y},{w},{h}) area={area}",flush=True)
        if area<100: continue
        component=labels==label; comp8=component.astype(np.uint8)*255
        outer=cv2.dilate(comp8,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(41,41)))>0
        inner=cv2.dilate(comp8,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(9,9)))>0
        samples=lab[outer & ~inner & ~mask]
        if len(samples)<50: remaining_total+=area; continue
        ref=np.median(samples,axis=0); lf=lab.astype(np.float32)
        compatible=(np.abs(lf[:,:,0]-ref[0])<48)&(np.abs(lf[:,:,1]-ref[1])<18)&(np.abs(lf[:,:,2]-ref[2])<18)&~mask
        compatible=cv2.morphologyEx(compatible.astype(np.uint8),cv2.MORPH_OPEN,np.ones((3,3),np.uint8))>0
        near_component=cv2.dilate(component.astype(np.uint8),cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(141,141)))>0
        allowed=compatible & near_component & ~mask
        print(f"[PatchDegradeWorker] COMPONENT {label} SURFACE allowed={int(np.count_nonzero(allowed))} elapsed={time.monotonic()-_comp_t0:.3f}s",flush=True)
        sn,sl,_,_=cv2.connectedComponentsWithStats(allowed.astype(np.uint8),8)
        near=cv2.dilate(component.astype(np.uint8),cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(17,17)))>0
        connected=np.zeros_like(allowed)
        for sid in range(1,sn):
            region=sl==sid
            if np.any(region & near): connected|=region
        allowed=connected; remaining=component.copy(); iterations=component_filled=0
        while np.any(remaining) and iterations<500:
            _now=time.monotonic()
            if _now-_comp_last>=5.0:
                print(f"[PatchDegradeWorker] COMPONENT {label} HEARTBEAT iteration={iterations} remaining={int(np.count_nonzero(remaining))} elapsed={_now-_comp_t0:.1f}s",flush=True)
                _comp_last=_now
            iterations+=1; eroded=cv2.erode(remaining.astype(np.uint8),np.ones((3,3),np.uint8),iterations=1)>0
            fy,fx=np.where(remaining & ~eroded)
            if not len(fx): break
            round_count=0
            for cy,cx in zip(fy[::2],fx[::2]):
                tx0,ty0,tx1,ty1=cx-4,cy-4,cx+5,cy+5
                if tx0<0 or ty0<0 or tx1>W or ty1>H: continue
                target=result[ty0:ty1,tx0:tx1]; local=remaining[ty0:ty1,tx0:tx1]; known=~local
                if np.count_nonzero(known)<12: continue
                best_score=best=None
                for sy in range(max(4,cy-70),min(H-4,cy+71),2):
                    for sx in range(max(4,cx-70),min(W-4,cx+71),2):
                        px0,py0,px1,py1=sx-4,sy-4,sx+5,sy+5
                        if np.mean(allowed[py0:py1,px0:px1])<.92: continue
                        src=clean[py0:py1,px0:px1]; a=target[known].astype(np.float32); b=src[known].astype(np.float32)
                        score=np.mean((a-b)**2)+(np.hypot(float(sx-cx),float(sy-cy))**2*.12)
                        if best_score is None or score<best_score: best_score,best=score,src
                if best is None: continue
                dest=result[ty0:ty1,tx0:tx1]; dest[local]=best[local]; result[ty0:ty1,tx0:tx1]=dest
                count=int(np.count_nonzero(local)); remaining[ty0:ty1,tx0:tx1][local]=False; component_filled+=count; round_count+=count
            if not round_count:
                print(f"[PatchDegradeWorker] COMPONENT {label} STOP iteration={iterations} remaining={int(np.count_nonzero(remaining))}",flush=True)
                break
        _rem=int(np.count_nonzero(remaining))
        print(f"[PatchDegradeWorker] COMPONENT {label} END iterations={iterations} filled={component_filled} remaining={_rem} elapsed={time.monotonic()-_comp_t0:.3f}s",flush=True)
        processed+=1; filled_total+=component_filled; remaining_total+=_rem
    result[~mask]=clean[~mask]
    if not cv2.imwrite(str(preview_path),result): raise RuntimeError("Falha ao gravar preview.")
    mp=int(np.count_nonzero(mask)); covered=max(0,mp-remaining_total)
    report={"algorithm":ALGORITHM,"components":processed,"mask_pixels":mp,"filled_pixels":covered,"remaining_pixels":remaining_total,"filled_percent":round(covered/mp*100 if mp else 0,4)}
    report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser(); p.add_argument("--worker",action="store_true"); p.add_argument("--clean"); p.add_argument("--mask"); p.add_argument("--preview"); p.add_argument("--report"); p.add_argument("--ranges"); a=p.parse_args()
    if not a.worker: raise SystemExit("Uso interno da Central.")
    _worker(Path(a.clean).resolve(),Path(a.mask).resolve(),Path(a.preview).resolve(),Path(a.report).resolve(),Path(a.ranges).resolve())
