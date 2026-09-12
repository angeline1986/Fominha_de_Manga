from __future__ import annotations
import hashlib, json, os, shutil, tempfile
from datetime import datetime, timezone
from pathlib import Path
from PIL import Image
from .review_state import build_pending_blocks, state_from_review_row, validate_page_range

PROPOSALS_DIRNAME="MERGE_MANUAL_PROPOSALS"
MANIFEST_NAME="merge-manual-manifest.json"

def _proposal_root(manga,chapter): return manga/"FLUXO_SECUNDARIO"/"01_MERGE_PROCESSAMENTO"/PROPOSALS_DIRNAME/str(chapter)
def _hash(path):
    d=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""): d.update(chunk)
    return d.hexdigest()
def _fp(x): return hashlib.sha256(json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()

def _selection(chapter_dir,review_row,block_id,start_file,end_file):
    current=state_from_review_row(review_row)
    if not current.get("eligible") or current.get("status")!="pending": raise ValueError("Capítulo sem residual autoritativo elegível.")
    blocks=build_pending_blocks(chapter_dir,current.get("pending_segments") or [])
    block=next((b for b in blocks if str(b.get("id"))==str(block_id)),None)
    if not block: raise ValueError("Bloco residual não existe mais.")
    selected=validate_page_range(block,start_file,end_file)
    by={str(p["file"]):p for p in block.get("pages") or []}
    return current,selected,[by[n] for n in selected["files"]]

def _cuts(cuts,total):
    vals=[]
    for raw in cuts:
        try:v=int(round(float(raw)))
        except Exception as e: raise ValueError("Coordenada de régua inválida.") from e
        if v<=0 or v>=total: raise ValueError(f"Corte fora da faixa elegível: Y {v}.")
        vals.append(v)
    if not vals: raise ValueError("Adicione pelo menos uma régua.")
    if len(vals)!=len(set(vals)): raise ValueError("Existem cortes duplicados.")
    return sorted(vals)

def _compose(chapter_dir,pages):
    total=sum(int(p["pending_height"]) for p in pages)
    if total<=0: raise ValueError("Faixa residual sem pixels elegíveis.")
    canvas=None;width=None;y=0
    try:
        for p in pages:
            path=chapter_dir/str(p["file"])
            try:
                with Image.open(path) as opened: img=opened.convert("RGB")
            except Exception as e: raise ValueError(f"Imagem fonte ilegível: {path.name}: {e}") from e
            if width is None: width=int(img.width);canvas=Image.new("RGB",(width,total))
            elif int(img.width)!=width: raise ValueError(f"Largura incompatível em {path.name}.")
            a,b=int(p["source_y_start"]),int(p["source_y_end"])
            if a<0 or b>img.height or b<=a: raise ValueError(f"Fatia residual inválida em {path.name}.")
            crop=img.crop((0,a,img.width,b));canvas.paste(crop,(0,y));y+=crop.height;crop.close()
        if canvas is None or y!=total: raise ValueError("Falha ao materializar faixa residual.")
        return canvas
    except Exception:
        if canvas is not None: canvas.close()
        raise

def generate_proposal(manga,chapter_dir,*,review_row,block_id,start_file,end_file,cuts):
    current,selected,pages=_selection(chapter_dir,review_row,block_id,start_file,end_file)
    total=sum(int(p["pending_height"]) for p in pages);cuts=_cuts(cuts,total)
    sources=[]
    for p in pages:
        path=chapter_dir/p["file"]
        if not path.is_file(): raise ValueError(f"Imagem fonte ausente: {path.name}.")
        st=path.stat();sources.append({"name":path.name,"size":st.st_size,"mtime_ns":st.st_mtime_ns,"sha256":_hash(path),"source_y_start":p["source_y_start"],"source_y_end":p["source_y_end"],"pending_height":p["pending_height"]})
    proposal_id=datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    root=_proposal_root(manga,chapter_dir.name);root.mkdir(parents=True,exist_ok=True);tmp=Path(tempfile.mkdtemp(prefix=f".{proposal_id}-",dir=str(root)));final=root/proposal_id
    canvas=None
    try:
        canvas=_compose(chapter_dir,pages);bounds=[0,*cuts,canvas.height];outputs=[]
        for i in range(len(bounds)-1):
            a,b=bounds[i],bounds[i+1]
            if b<=a: raise ValueError("Corte gerou bloco vazio.")
            block=canvas.crop((0,a,canvas.width,b));name=f"block-{i+1:03d}.png";block.save(tmp/name,"PNG");block.close()
            outputs.append({"block":i+1,"file":name,"relative_start":a,"relative_end":b,"global_start":selected["global_start"]+a,"global_end":selected["global_start"]+b,"height":b-a,"width":canvas.width})
        review_snapshot={"source":current.get("source"),"block_id":block_id,"global_start":selected["global_start"],"global_end":selected["global_end"],"pending_segments":current.get("pending_segments") or []}
        manifest={"schema":"manual_merge_proposal_v1","proposal_id":proposal_id,"chapter":chapter_dir.name,"created_at":datetime.now(timezone.utc).isoformat(),"status":"PROPOSTA_GERADA","review_source":{"stage":"REVIEW_MERGE","authoritative_source":current.get("source"),"review_fingerprint":_fp(review_snapshot)},"source_block":{"block_id":block_id,"start":start_file,"end":end_file,"global_start":selected["global_start"],"global_end":selected["global_end"],"height":total},"source_files":sources,"source_fingerprint":_fp(sources),"cuts":cuts,"outputs":outputs,"safety":{"official_merge_modified":False,"only_uncovered_pixels_materialized":True}}
        (tmp/MANIFEST_NAME).write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8");os.replace(tmp,final);return manifest
    except Exception: shutil.rmtree(tmp,ignore_errors=True);raise
    finally:
        if canvas is not None: canvas.close()

def latest_proposal(manga,chapter):
    root=_proposal_root(manga,chapter)
    if not root.is_dir(): return None
    for folder in sorted([p for p in root.iterdir() if p.is_dir()],key=lambda p:p.name,reverse=True):
        mp=folder/MANIFEST_NAME
        if not mp.is_file(): continue
        try:data=json.loads(mp.read_text(encoding="utf-8"))
        except Exception: continue
        if data.get("status") in {"PROPOSTA_GERADA","EFETIVADO"}: return data
    return None

def proposal_dir(manga,chapter,proposal_id):
    root=_proposal_root(manga,chapter).resolve();target=(root/str(proposal_id)).resolve()
    if not target.is_relative_to(root): raise ValueError("proposal_id inválido.")
    return target
