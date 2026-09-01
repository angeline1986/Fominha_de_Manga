#!/usr/bin/env python3
from __future__ import annotations
import json, mimetypes, os, re, shutil, subprocess, sys, threading, traceback, urllib.parse, webbrowser
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT/"download"/"mangago_downloader"/"output"
STATIC=Path(__file__).resolve().parent
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
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
def merge_status_file(ch): return ch.parent.parent/"FLUXO_SECUNDARIO"/"MERGE_STATUS"/ch.name/"merge-attempt.json"

def set_merge_failure(ch,message):
    p=merge_status_file(ch); p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps({"schema_version":1,"chapter":ch.name,"status":"error","message":str(message)},ensure_ascii=False,indent=2),encoding="utf-8")

def clear_merge_failure(ch):
    p=merge_status_file(ch)
    if p.is_file(): p.unlink()
    if p.parent.is_dir() and not any(p.parent.iterdir()): p.parent.rmdir()

def catalog():
    out={}
    for provider in ("comix","mangago"):
        p=OUTPUT/provider
        out[provider]=sorted([x.name for x in p.iterdir() if x.is_dir() and (x/"IMG").is_dir()],key=nkey) if p.is_dir() else []
    return out




def review_merge_items(manga, ch):
    """
    Mapeia cada merged-xxx para as páginas que entram no merge e para uma
    janela de análise de até max_source_images, incluindo contexto após o corte.
    """
    rd = rdir(manga, ch.name)
    mf = rd / "merge-review.json"
    if not mf.is_file():
        return []
    try:
        payload = json.loads(mf.read_text(encoding="utf-8"))
        boundaries = [int(x) for x in (payload.get("boundaries") or [])]
        outputs = sorted(rd.glob("merged-*.png"), key=nkey)
        policy = payload.get("policy") or {}
        try:
            max_sources = int(policy.get("max_source_images") or 8)
        except (TypeError, ValueError):
            max_sources = 8
        max_sources = max(2, min(50, max_sources))

        if len(boundaries) != len(outputs) + 1:
            return [{"file":p.name,"index":i+1,"sources":[],"source_spans":[],
                     "analysis_sources":[],"analysis_limit":max_sources}
                    for i,p in enumerate(outputs)]

        source_names = payload.get("source_pages") or []
        source_dir = manga / "IMG" / ch.name
        spans = []
        y = 0
        from PIL import Image
        for source_index, name in enumerate(source_names):
            p = source_dir / name
            if not p.is_file():
                continue
            with Image.open(p) as im:
                h = int(im.height)
            spans.append({
                "file": name,
                "source_index": source_index,
                "global_start": y,
                "global_end": y + h,
                "height": h,
            })
            y += h

        items = []
        for i, out in enumerate(outputs):
            start, end = boundaries[i], boundaries[i + 1]
            source_spans = []
            for sp in spans:
                a, b = sp["global_start"], sp["global_end"]
                overlap_start = max(start, a)
                overlap_end = min(end, b)
                if overlap_end <= overlap_start:
                    continue
                source_spans.append({
                    "file": sp["file"],
                    "source_index": sp["source_index"],
                    "merge_start": overlap_start - start,
                    "merge_end": overlap_end - start,
                    "source_start": overlap_start - a,
                    "source_end": overlap_end - a,
                    "source_height": sp["height"],
                })

            included_indexes = {x["source_index"] for x in source_spans}
            first_index = source_spans[0]["source_index"] if source_spans else 0
            window = [sp for sp in spans
                      if first_index <= sp["source_index"] < first_index + max_sources]

            analysis_sources = [{
                "file": sp["file"],
                "source_index": sp["source_index"],
                "included": sp["source_index"] in included_indexes,
                "height": sp["height"],
            } for sp in window]

            items.append({
                "file": out.name,
                "index": i + 1,
                "global_start": start,
                "global_end": end,
                "sources": [x["file"] for x in source_spans],
                "source_spans": source_spans,
                "analysis_sources": analysis_sources,
                "analysis_limit": max_sources,
                "included_count": sum(1 for x in analysis_sources if x["included"]),
                "context_count": sum(1 for x in analysis_sources if not x["included"]),
            })
        return items
    except Exception as exc:
        print(f"[processing-web] Falha ao mapear fontes do review cap {ch.name}: {exc}")
        return []

def review_max_source_images(rd):
    mf=rd/"merge-review.json"
    if not mf.is_file(): return None
    try:
        payload=json.loads(mf.read_text(encoding="utf-8"))
        value=(payload.get("policy") or {}).get("max_source_images")
        return int(value) if value is not None else None
    except Exception:
        return None

def pdf_merge_files(manga, chapter):
    try:
        folder=manga/"FLUXO_SECUNDARIO"/"PDF_MERGE"/str(chapter)
        if not folder.is_dir():
            return []
        return [p.name for p in sorted(folder.glob("*.pdf"), key=nkey) if p.is_file()]
    except Exception:
        return []


def latest_pdf_merge_batch(manga):
    root = manga / "FLUXO_SECUNDARIO" / "PDF_MERGE"
    if not root.is_dir():
        return []
    items = []
    for p in root.rglob("*.pdf"):
        if not p.is_file():
            continue
        try:
            mtime = p.stat().st_mtime
        except OSError:
            continue
        try:
            chapter = p.parent.relative_to(root).parts[0]
        except Exception:
            chapter = p.parent.name
        items.append({"file": p.name, "chapter": str(chapter), "mtime": float(mtime)})
    if not items:
        return []
    newest = max(x["mtime"] for x in items)
    batch = [x for x in items if newest - x["mtime"] <= 12.0]
    batch.sort(key=lambda x: (str(x["chapter"]), x["file"]))
    return batch

def row_state(manga,ch):
    from processamento.unificacao_imagens.image_stitcher import is_chapter_merged, merge_output_dir
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
        "merge_failed":merge_status_file(ch).is_file(),
        "merge_state":"concluido" if merge_ok else ("pendente" if merge_status_file(ch).is_file() else "novo"),
        "merged_images":len(list(md.glob("merged-*.png"))) if md.is_dir() else 0,
        "review":(rd/"merge-review.json").is_file(),
        "review_images":len(list(rd.glob("merged-*.png"))) if rd.is_dir() else 0,
        "review_files":[p.name for p in sorted(rd.glob("merged-*.png"),key=nkey)] if rd.is_dir() else [],
        "review_merges":review_merge_items(manga,ch),
        "review_max_source_images":review_max_source_images(rd),
        "clean":(cdir(manga,ch.name)/"clean-manifest.json").is_file(),
        "pdf":(manga/"PDF"/ch.name/f"{ch.name}.pdf").is_file(),
        "pdf_merge":(pmdir(manga,ch.name)/f"{ch.name}.pdf").is_file(),
    }

def state(provider,manga_name):
    manga=manga_path(provider,manga_name); rows=[row_state(manga,ch) for ch in chapters(manga)]
    return {"provider":provider,"manga":manga_name,"chapters":rows,"summary":{
        "chapters":len(rows),"merges":sum(x["merge"] for x in rows),
        "pending":sum(x["merge_state"]=="pendente" for x in rows),
        "new":sum(x["merge_state"]=="novo" for x in rows),
        "merge_failed":sum(x["merge_failed"] for x in rows),
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
            elif job.action=="review_generate": job.result=do_review_generate(job,manga,chs,payload.get("max_source_images"))
            elif job.action=="review_approve": job.result=do_review_approve(job,manga,chs)
            elif job.action=="review_reject": job.result=do_review_reject(job,manga,chs)
            else: raise ValueError("Ação inválida.")
            job.status="done"; job.message="Processamento concluído."
    except Exception as e:
        job.status="error"; job.error=str(e); job.message=str(e); traceback.print_exc()

def do_merge(job,chs):
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from processamento.unificacao_imagens.image_stitcher import is_chapter_merged, merge_chapter

    def process_one(ch):
        try:
            if is_chapter_merged(ch):
                clear_merge_failure(ch)
                return {"chapter":ch.name,"status":"skipped","message":"MERGE já existente"}
            r=merge_chapter(ch)
            clear_merge_failure(ch)
            return {"chapter":ch.name,"status":"ok","merged_images":r.merged_images}
        except Exception as e:
            set_merge_failure(ch,e)
            return {"chapter":ch.name,"status":"error","message":str(e)}

    out=[]
    total=len(chs)
    with ThreadPoolExecutor(max_workers=3, thread_name_prefix="merge-v3") as executor:
        futures={executor.submit(process_one,ch):ch for ch in chs}
        for i,future in enumerate(as_completed(futures),1):
            item=future.result()
            out.append(item)
            job.progress=i
            remaining=max(0,total-i)
            active=min(3,remaining)
            job.message=f"Unificação: {i}/{total} concluído(s)"
            if active:
                job.message+=f" · até {active} em processamento"

    order={ch.name:i for i,ch in enumerate(chs)}
    out.sort(key=lambda item:order.get(item.get("chapter"),999999))
    return out

def do_pdf(job,chs):
    from orquestracao.menu import run_pdf_batch
    job.message="Validando imagens e gerando PDFs..."
    r=run_pdf_batch(chs,regenerate_existing=False); job.progress=len(chs)
    return {"selected":r["selected"],"generated":[x.name for x in r["generated"]],"skipped":[x.name for x in r["skipped"]],"problems":[{"chapter":c.name,"message":m} for c,m in r["problems"]]}

def pdf_generator():
    d=ROOT/"download"/"mangago_downloader"
    if str(d) not in sys.path: sys.path.insert(0,str(d))
    from src.pdf.generator import generate_pdf_from_images
    return generate_pdf_from_images

def do_pdf_merge(job,manga,chs):
    from processamento.unificacao_imagens.image_stitcher import is_chapter_merged, merge_output_dir
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
    from processamento.limpeza_baloes.bubble_cleaner import EasyOCRBackend,process_image,resolve_model
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
    from processamento.unificacao_imagens import image_stitcher_review
    return image_stitcher_review

def do_review_generate(job,manga,chs,max_source_images=None):
    rv=reviewmod(); out=[]
    try:
        limit=int(max_source_images) if max_source_images is not None else 8
    except (TypeError,ValueError):
        raise ValueError("Máximo de imagens por merge inválido.")
    if not 2 <= limit <= 50:
        raise ValueError("Máximo de imagens por merge deve ficar entre 2 e 50.")
    for i,ch in enumerate(chs,1):
        job.message=f"Gerando proposta para capítulo {ch.name} · máximo {limit} originais/merge..."
        try:
            ok,msg,dest=rv.generate_candidate(manga, ch, max_source_images=limit)
        except rv.ReviewSourceLimitError as exc:
            item=exc.as_dict()
            item["chapter"]=str(ch)
            item["max_source_images"]=int(limit)
            out.append(item)
            job.progress=i
            continue
        out.append({"chapter":ch.name,"status":"ok" if ok else "error","message":msg,"path":str(dest) if dest else None,"max_source_images":limit})
        job.progress=i
    return out

def do_review_approve(job,manga,chs):
    from processamento.unificacao_imagens.image_stitcher import is_chapter_merged
    rv=reviewmod(); out=[]
    for i,ch in enumerate(chs,1):
        job.message=f"Aprovando capítulo {ch.name}..."
        try:
            approved=rv.approve(manga,ch.name)
            if not isinstance(approved,(tuple,list)) or len(approved)<2:
                raise TypeError(f"approve() retornou formato inesperado: {type(approved).__name__}: {approved!r}")
            ok,msg=approved[0],approved[1]
        except Exception as exc:
            out.append({"chapter":ch.name,"status":"error","message":f"Falha ao aprovar proposta ({type(exc).__name__}): {exc}"})
            job.progress=i
            continue
        if ok and is_chapter_merged(ch):
            rd=rdir(manga,ch.name)
            if rd.is_dir(): shutil.rmtree(rd)
            clear_merge_failure(ch)
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
            if u.path=="/api/pdf-merge-latest":
                manga=manga_path(q.get("provider",[""])[0],q.get("manga",[""])[0])
                files=latest_pdf_merge_batch(manga)
                return self.send_json({"ok":True,"files":files})
            if u.path=="/api/pdf-merge-files":
                manga=manga_path(q.get("provider",[""])[0],q.get("manga",[""])[0])
                chapter=str(q.get("chapter",[""])[0])
                return self.send_json({"ok":True,"chapter":chapter,"files":pdf_merge_files(manga,chapter)})
            if u.path=="/api/open-folder":
                manga=manga_path(q.get("provider",[""])[0],q.get("manga",[""])[0])
                chapter=str(q.get("chapter",[""])[0])
                kind=str(q.get("kind",["merge"])[0]).lower()
                folder_name="PDF_MERGE" if kind=="pdf_merge" else "MERGE"
                base=(manga/"FLUXO_SECUNDARIO"/folder_name).resolve()
                target=base if (kind=="pdf_merge" and not chapter) else (base/chapter).resolve()
                if not target.is_relative_to(base) or not target.is_dir():
                    raise ValueError(f"Pasta {folder_name} não encontrada.")
                subprocess.Popen(["open",str(target)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                return self.send_json({"ok":True,"message":"Pasta aberta."})
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
        manga=manga_path(q.get("provider",[""])[0],q.get("manga",[""])[0])
        chapter=q.get("chapter",[""])[0]
        kind=q.get("kind",["review"])[0]
        if kind=="review":
            base=rdir(manga,chapter).resolve()
        elif kind=="source":
            base=(manga/"IMG"/chapter).resolve()
        else:
            self.send_error(404); return
        target=(base/q.get("file",[""])[0]).resolve()
        if not target.is_relative_to(base) or not target.is_file() or target.suffix.lower() not in IMAGE_EXTS: self.send_error(404); return
        raw=target.read_bytes(); self.send_response(200); self.send_header("Content-Type",mimetypes.guess_type(target.name)[0] or "image/png"); self.send_header("Content-Length",str(len(raw))); self.send_header("Cache-Control","no-store"); self.end_headers(); self.wfile.write(raw)

def main():
    if not STATIC.is_dir(): raise SystemExit(f"Frontend não encontrado: {STATIC}")
    s=ThreadingHTTPServer((HOST,PORT),Handler); url=f"http://{HOST}:{PORT}"; print(f"Central de Processamento: {url}"); threading.Timer(.6,lambda:webbrowser.open(url)).start()
    try:s.serve_forever()
    except KeyboardInterrupt:pass
    finally:s.server_close()

if __name__=="__main__":main()
