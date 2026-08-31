#!/usr/bin/env python3
from __future__ import annotations
import json, mimetypes, os, re, shutil, sys, threading, traceback, urllib.parse, webbrowser
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parent
OUTPUT=ROOT/"mangago_downloader"/"output"
STATIC=ROOT/"processing_web"
HOST="127.0.0.1"
PORT=int(os.environ.get("FOMINHA_PROCESSING_PORT","8766"))
IMAGE_EXTS={".png",".jpg",".jpeg",".webp"}

def nkey(v):
    n=v.name if isinstance(v,Path) else str(v)
    return [int(x) if x.isdigit() else x.lower() for x in re.split(r"(\d+)",n)]

def manga_path(provider,manga):
    if provider not in {"comix","mangago"}: raise ValueError("Provider inválido.")
    base=(OUTPUT/provider).resolve(); target=(base/manga).resolve()
    if not target.is_relative_to(base) or not target.is_dir(): raise ValueError("Obra inválida.")
    return target

def chapters(manga):
    root=manga/"IMG"
    if not root.is_dir(): return []
    return sorted([p for p in root.iterdir() if p.is_dir() and any(f.is_file() and f.suffix.lower() in IMAGE_EXTS for f in p.iterdir())],key=nkey)

def rdir(m,c): return m/"FLUXO_SECUNDARIO"/"MERGE_REVIEW"/c
def cdir(m,c): return m/"FLUXO_SECUNDARIO"/"CLEAN"/c
def pmdir(m,c): return m/"FLUXO_SECUNDARIO"/"PDF_MERGE"/c

def catalog():
    out={}
    for provider in ("comix","mangago"):
        p=OUTPUT/provider
        out[provider]=sorted([x.name for x in p.iterdir() if x.is_dir() and (x/"IMG").is_dir()],key=nkey) if p.is_dir() else []
    return out

def row_state(manga,ch):
    from image_stitcher import is_chapter_merged, merge_output_dir
    md=merge_output_dir(ch); rd=rdir(manga,ch.name)
    merge_ok=False
    merge_error=None
    try:
        merge_ok=bool(is_chapter_merged(ch))
    except Exception as exc:
        merge_error=str(exc)
    return {
        "chapter":ch.name,
        "pages":sum(1 for p in ch.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTS and p.name.lower().startswith("page-")),
        "merge":merge_ok,
        "merge_error":merge_error,
        "merged_images":len(list(md.glob("merged-*.png"))) if md.is_dir() else 0,
        "review":(rd/"merge-review.json").is_file(),
        "review_images":len(list(rd.glob("merged-*.png"))) if rd.is_dir() else 0,
        "clean":(cdir(manga,ch.name)/"clean-manifest.json").is_file(),
        "pdf":(manga/"PDF"/ch.name/f"{ch.name}.pdf").is_file(),
        "pdf_merge":(pmdir(manga,ch.name)/f"{ch.name}.pdf").is_file(),
    }

def state(provider,manga_name):
    manga=manga_path(provider,manga_name); rows=[row_state(manga,ch) for ch in chapters(manga)]
    return {"provider":provider,"manga":manga_name,"chapters":rows,"summary":{
        "chapters":len(rows),"merges":sum(x["merge"] for x in rows),"pending":sum(not x["merge"] for x in rows),
        "review":sum(x["review"] for x in rows),"pdfs":sum(x["pdf"] for x in rows),"clean":sum(x["clean"] for x in rows),
        "pdf_merge":sum(x["pdf_merge"] for x in rows)}}

@dataclass
class Job:
    id:int; action:str; status:str="queued"; progress:int=0; total:int=0; message:str=""; error:str|None=None; result:Any=None

JOBS={}; COUNTER=0; LOCK=threading.Lock(); OPLOCK=threading.Lock()

def make_job(action,payload):
    global COUNTER
    with LOCK:
        COUNTER+=1; j=Job(COUNTER,action); JOBS[j.id]=j
    threading.Thread(target=run_job,args=(j,payload),daemon=True).start()
    return j

def selected(manga,names):
    d={p.name:p for p in chapters(manga)}
    if not names: raise ValueError("Nenhum capítulo selecionado.")
    try:return [d[str(n)] for n in names]
    except KeyError as e: raise ValueError(f"Capítulo inválido: {e.args[0]}")

def run_job(job,payload):
    try:
        with OPLOCK:
            job.status="running"; manga=manga_path(str(payload.get("provider","")),str(payload.get("manga",""))); chs=selected(manga,payload.get("chapters") or []); job.total=len(chs)
            if job.action=="merge": job.result=do_merge(job,chs)
            elif job.action=="pdf": job.result=do_pdf(job,chs)
            elif job.action=="pdf_merge": job.result=do_pdf_merge(job,manga,chs)
            elif job.action=="clean": job.result=do_clean(job,manga,chs)
            elif job.action=="review_generate": job.result=do_review_generate(job,manga,chs)
            elif job.action=="review_approve": job.result=do_review_approve(job,manga,chs)
            elif job.action=="review_reject": job.result=do_review_reject(job,manga,chs)
            else: raise ValueError("Ação inválida.")
            job.status="done"; job.message="Processamento concluído."
    except Exception as e:
        job.status="error"; job.error=str(e); job.message=str(e); traceback.print_exc()

def do_merge(job,chs):
    from image_stitcher import is_chapter_merged, merge_chapter
    out=[]
    for i,ch in enumerate(chs,1):
        job.message=f"Unificando capítulo {ch.name}..."
        if is_chapter_merged(ch): out.append({"chapter":ch.name,"status":"skipped","message":"MERGE já existente"})
        else:
            try:
                r=merge_chapter(ch); out.append({"chapter":ch.name,"status":"ok","merged_images":r.merged_images})
            except Exception as e: out.append({"chapter":ch.name,"status":"error","message":str(e)})
        job.progress=i
    return out

def do_pdf(job,chs):
    from menu import run_pdf_batch
    job.message="Validando imagens e gerando PDFs..."
    r=run_pdf_batch(chs,regenerate_existing=False); job.progress=len(chs)
    return {"selected":r["selected"],"generated":[x.name for x in r["generated"]],"skipped":[x.name for x in r["skipped"]],"problems":[{"chapter":c.name,"message":m} for c,m in r["problems"]]}

def pdf_generator():
    d=ROOT/"mangago_downloader"
    if str(d) not in sys.path: sys.path.insert(0,str(d))
    from src.pdf.generator import generate_pdf_from_images
    return generate_pdf_from_images

def do_pdf_merge(job,manga,chs):
    from image_stitcher import is_chapter_merged, merge_output_dir
    gen=pdf_generator(); out=[]
    for i,ch in enumerate(chs,1):
        job.message=f"Gerando PDF do Merge: {ch.name}..."
        if not is_chapter_merged(ch): out.append({"chapter":ch.name,"status":"error","message":"MERGE oficial inválido ou ausente"}); job.progress=i; continue
        imgs=sorted(merge_output_dir(ch).glob("merged-*.png"),key=nkey); destdir=pmdir(manga,ch.name); destdir.mkdir(parents=True,exist_ok=True); dest=destdir/f"{ch.name}.pdf"
        if dest.is_file(): out.append({"chapter":ch.name,"status":"skipped","message":"PDF do Merge já existente"})
        else:
            gen([str(p) for p in imgs],str(dest)); out.append({"chapter":ch.name,"status":"ok","pages":len(imgs),"path":str(dest)})
        job.progress=i
    return out

def do_clean(job,manga,chs):
    from bubble_cleaner import EasyOCRBackend,process_image,resolve_model
    model=resolve_model(None); ocr=EasyOCRBackend(["en"]); out=[]
    for i,ch in enumerate(chs,1):
        target=cdir(manga,ch.name); target.mkdir(parents=True,exist_ok=True); imgs=sorted([p for p in ch.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTS],key=nkey); reports=[]; fails=[]
        for pi,img in enumerate(imgs,1):
            job.message=f"Capítulo {ch.name}: página {pi}/{len(imgs)}"
            try: reports.append(process_image(img,target,model,["en"],0.55,ocr_backend=ocr))
            except Exception as e: fails.append(f"{img.name}: {e}")
        manifest={"schema_version":1,"algorithm":"bubble_cleaner_v3_5","source_immutable":True,"pages_total":len(reports),"integrity_ok":bool(reports) and all(r["summary"]["integrity_ok"] for r in reports) and not fails,"failures":fails}
        (target/"clean-manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
        out.append({"chapter":ch.name,"status":"ok" if not fails else "error","pages":len(reports),"failures":fails}); job.progress=i
    return out

def reviewmod():
    import image_stitcher_review
    return image_stitcher_review

def do_review_generate(job,manga,chs):
    rv=reviewmod(); out=[]
    for i,ch in enumerate(chs,1):
        job.message=f"Gerando proposta para capítulo {ch.name}..."
        ok,msg,dest=rv.generate_candidate(manga,ch); out.append({"chapter":ch.name,"status":"ok" if ok else "error","message":msg,"path":str(dest) if dest else None}); job.progress=i
    return out

def do_review_approve(job,manga,chs):
    from image_stitcher import is_chapter_merged
    rv=reviewmod(); out=[]
    for i,ch in enumerate(chs,1):
        job.message=f"Aprovando capítulo {ch.name}..."
        ok,msg=rv.approve(manga,ch.name)
        if ok and is_chapter_merged(ch):
            rd=rdir(manga,ch.name)
            if rd.is_dir(): shutil.rmtree(rd)
            out.append({"chapter":ch.name,"status":"ok","message":msg})
        else: out.append({"chapter":ch.name,"status":"error","message":msg if not ok else "MERGE promovido, mas manifesto oficial não reconhecido."})
        job.progress=i
    return out

def do_review_reject(job,manga,chs):
    out=[]
    for i,ch in enumerate(chs,1):
        rd=rdir(manga,ch.name)
        if rd.is_dir(): shutil.rmtree(rd)
        out.append({"chapter":ch.name,"status":"ok","message":"Proposta removida; IMG e MERGE preservados."}); job.progress=i
    return out

class Handler(BaseHTTPRequestHandler):
    def log_message(self,fmt,*args): print("[processing-web]",fmt%args)
    def send_json(self,p,status=200):
        raw=json.dumps(p,ensure_ascii=False).encode(); self.send_response(status); self.send_header("Content-Type","application/json; charset=utf-8"); self.send_header("Content-Length",str(len(raw))); self.send_header("Cache-Control","no-store"); self.end_headers(); self.wfile.write(raw)
    def body(self):
        n=int(self.headers.get("Content-Length","0")); raw=self.rfile.read(n); return json.loads(raw.decode()) if raw else {}
    def do_GET(self):
        u=urllib.parse.urlparse(self.path); q=urllib.parse.parse_qs(u.query)
        try:
            if u.path=="/api/catalog": return self.send_json(catalog())
            if u.path=="/api/state": return self.send_json(state(q.get("provider",[""])[0],q.get("manga",[""])[0]))
            if u.path=="/api/shutdown":
                self.send_json({"ok":True,"message":"Servidor finalizado."})
                threading.Thread(target=self.server.shutdown,daemon=True).start()
                return
            if u.path.startswith("/api/job/"):
                j=JOBS.get(int(u.path.rsplit("/",1)[-1])); return self.send_json(j.__dict__ if j else {"error":"Job não encontrado."},200 if j else 404)
            if u.path=="/media": return self.media(q)
            return self.static(u.path)
        except Exception as e:return self.send_json({"error":str(e)},400)
    def do_POST(self):
        if urllib.parse.urlparse(self.path).path!="/api/action": return self.send_json({"error":"Rota não encontrada."},404)
        try:
            b=self.body(); j=make_job(str(b.get("action","")),b); return self.send_json({"job_id":j.id},HTTPStatus.ACCEPTED)
        except Exception as e:return self.send_json({"error":str(e)},400)
    def static(self,path):
        rel="index.html" if path in {"","/"} else path.lstrip("/"); target=(STATIC/rel).resolve(); base=STATIC.resolve()
        if not target.is_relative_to(base) or not target.is_file(): self.send_error(404); return
        raw=target.read_bytes(); self.send_response(200); self.send_header("Content-Type",mimetypes.guess_type(target.name)[0] or "application/octet-stream"); self.send_header("Content-Length",str(len(raw))); self.end_headers(); self.wfile.write(raw)
    def media(self,q):
        manga=manga_path(q.get("provider",[""])[0],q.get("manga",[""])[0]); base=rdir(manga,q.get("chapter",[""])[0]).resolve(); target=(base/q.get("file",[""])[0]).resolve()
        if not target.is_relative_to(base) or not target.is_file() or target.suffix.lower() not in IMAGE_EXTS: self.send_error(404); return
        raw=target.read_bytes(); self.send_response(200); self.send_header("Content-Type",mimetypes.guess_type(target.name)[0] or "image/png"); self.send_header("Content-Length",str(len(raw))); self.send_header("Cache-Control","no-store"); self.end_headers(); self.wfile.write(raw)

def main():
    if not STATIC.is_dir(): raise SystemExit(f"Frontend não encontrado: {STATIC}")
    s=ThreadingHTTPServer((HOST,PORT),Handler); url=f"http://{HOST}:{PORT}"; print(f"Central de Processamento: {url}"); threading.Timer(.6,lambda:webbrowser.open(url)).start()
    try:s.serve_forever()
    except KeyboardInterrupt:pass
    finally:s.server_close()

if __name__=="__main__":main()
