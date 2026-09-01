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
def l2dir(m,c): return m/"FLUXO_SECUNDARIO"/"MERGE_LEVEL2"/c
def cdir(m,c): return m/"FLUXO_SECUNDARIO"/"CLEAN"/c
def pmdir(m,c): return m/"FLUXO_SECUNDARIO"/"PDF_MERGE"/c
def merge_status_file(ch): return ch.parent.parent/"FLUXO_SECUNDARIO"/"MERGE_STATUS"/ch.name/"merge-attempt.json"


def _segment_source_names(infos,start,end):
    return [info.path.name for info in infos if min(int(end),int(info.global_end)) > max(int(start),int(info.global_start))]

def _segment_bounds(infos,start,end):
    sources=[]
    for info in infos:
        lo=max(int(start),int(info.global_start)); hi=min(int(end),int(info.global_end))
        if hi<=lo: continue
        sources.append({
            "file":info.path.name,
            "global_start":int(info.global_start),"global_end":int(info.global_end),
            "source_y_start":int(lo-info.global_start),
            "source_y_end":int(hi-info.global_start),
        })
    return sources

def _page_range_label(sources):
    if not sources: return "Y ?"
    names=[x["file"] if isinstance(x,dict) else str(x) for x in sources]
    return names[0] if names[0]==names[-1] else f"{names[0]} → {names[-1]}"

def _passed_segment(index,start,end,infos):
    sources=_segment_bounds(infos,start,end)
    return {
        "id":index,"index":index,"status":"passed","validation":"auto",
        "global_start":int(start),"global_end":int(end),"height":int(end-start),
        "sources":[x["file"] for x in sources],"source_spans":sources,
        "label":_page_range_label(sources),
    }

def _failed_segment(index,start,end,infos,reason="auto_merge_oversized_chunk"):
    sources=_segment_bounds(infos,start,end)
    return {
        "id":index,"index":index,"status":"failed","validation":"review_required",
        "global_start":int(start),"global_end":int(end),"height":int(end-start),
        "sources":[x["file"] for x in sources],"source_spans":sources,
        "label":_page_range_label(sources),"reason":reason,
    }

def _v3_cuts_from(origin,total,bands):
    shifted=[]
    for b in bands:
        if b.end<=origin: continue
        class B: pass
        x=B(); x.start=b.start-origin; x.end=b.end-origin
        x.height=b.height; x.white_ratio_mean=b.white_ratio_mean
        shifted.append(x)
    from processamento.unificacao_imagens import image_stitcher as v3
    cuts,_=v3.choose_cuts(
        total-origin,shifted,
        target_height=v3.DEFAULT_TARGET_HEIGHT,
        search_before=v3.DEFAULT_SEARCH_BEFORE,
        search_after=v3.DEFAULT_SEARCH_AFTER,
        min_chunk_height=v3.DEFAULT_MIN_CHUNK_HEIGHT,
        min_white_band=v3.DEFAULT_MIN_WHITE_BAND,
        max_chunk_height=v3.DEFAULT_MAX_CHUNK_HEIGHT,
    )
    out=[]
    for c in cuts:
        item=dict(c); item["center"]=int(item["center"])+origin
        if "band_start" in item: item["band_start"]=int(item["band_start"])+origin
        if "band_end" in item: item["band_end"]=int(item["band_end"])+origin
        out.append(item)
    return out

def _next_safe_band_after(start,total,bands):
    from processamento.unificacao_imagens import image_stitcher as v3
    lower=int(start)+int(v3.DEFAULT_MAX_CHUNK_HEIGHT)
    upper=int(total)-int(v3.DEFAULT_MIN_CHUNK_HEIGHT)
    candidates=[]
    for b in bands:
        center=(int(b.start)+int(b.end))//2
        if center<=lower or center>upper: continue
        if int(b.height)<int(v3.DEFAULT_MIN_WHITE_BAND): continue
        candidates.append(center)
    return min(candidates) if candidates else None

def _analyze_merge_partition(ch):
    try:
        from processamento.unificacao_imagens import image_stitcher as v3
        pages=v3.list_pages(ch)
        if not pages: return None
        infos,bands,total,_=v3.analyze_chapter(
            pages,
            sample_width=v3.DEFAULT_SAMPLE_WIDTH,
            light_threshold=v3.DEFAULT_LIGHT_THRESHOLD,
            white_ratio_threshold=v3.DEFAULT_WHITE_RATIO,
        )
        cuts=_v3_cuts_from(0,total,bands)
        bounds=[0]+[int(c["center"]) for c in cuts]+[int(total)]
        segments=[]; idx=1
        for start,end in zip(bounds,bounds[1:]):
            if end-start<=int(v3.DEFAULT_MAX_CHUNK_HEIGHT):
                segments.append(_passed_segment(idx,start,end,infos)); idx+=1
                continue
            rescue=_next_safe_band_after(start,total,bands)
            if rescue:
                segments.append(_failed_segment(idx,start,rescue,infos)); idx+=1
                cont=[rescue]+[int(c["center"]) for c in _v3_cuts_from(rescue,total,bands)]+[int(total)]
                for a,b in zip(cont,cont[1:]):
                    if b-a<=int(v3.DEFAULT_MAX_CHUNK_HEIGHT):
                        segments.append(_passed_segment(idx,a,b,infos)); idx+=1
                    else:
                        segments.append(_failed_segment(idx,a,b,infos)); idx+=1
                break
            segments.append(_failed_segment(idx,start,end,infos)); idx+=1
        pending=[x for x in segments if x["status"]=="failed"]
        if not pending: return None
        resolved=[x for x in segments if x["status"]=="passed"]
        pending_sources={name for seg in pending for name in (seg.get("sources") or [])}
        resolved_sources={name for seg in resolved for name in (seg.get("sources") or [])}
        resolved_only=resolved_sources-pending_sources
        return {
            "schema_version":2,
            "algorithm":"whitespace_v3_level2_partition",
            "status":"partial" if resolved else "pending_review",
            "level2_validated":False,
            "max_chunk_height":int(v3.DEFAULT_MAX_CHUNK_HEIGHT),
            "total_height":int(total),
            "source_pages_count":len(pages),
            "segments":segments,
            "resolved_segments":resolved,
            "pending_segments":pending,
            "resolved_source_pages":sorted(resolved_only,key=nkey),
            "pending_source_pages":sorted(pending_sources,key=nkey),
            "resolved_source_pages_count":len(resolved_only),
            "pending_source_pages_count":len(pending_sources),
            "pending_segments_count":len(pending),
            "resolved_segments_count":len(resolved),
        }
    except Exception as exc:
        print(f"[processing-web] Falha ao classificar trechos do merge cap {ch.name}: {exc}")
        return None

def read_merge_failure(ch):
    p=merge_status_file(ch)
    if not p.is_file(): return None
    try:
        payload=json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"schema_version":1,"chapter":ch.name,"status":"error","message":"Falha de merge não legível."}
    part_payload=payload.get("partition") or {}
    if not payload.get("partition") or int(part_payload.get("schema_version") or 0)<2:
        part=_analyze_merge_partition(ch)
        if part:
            payload["partition"]=part
            try: p.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
            except Exception as exc: print(f"[processing-web] Não foi possível persistir partição do cap {ch.name}: {exc}")
    return payload

def set_merge_failure(ch,message):
    p=merge_status_file(ch); p.parent.mkdir(parents=True,exist_ok=True)
    payload={"schema_version":2,"chapter":ch.name,"status":"error","message":str(message)}
    part=_analyze_merge_partition(ch)
    if part: payload["partition"]=part
    p.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")

def clear_merge_failure(ch):
    p=merge_status_file(ch)
    if p.is_file(): p.unlink()
    if p.parent.is_dir() and not any(p.parent.iterdir()): p.parent.rmdir()

def validate_merge_level2(ch):
    from PIL import Image
    failure=read_merge_failure(ch)
    if not failure: return False,"Nenhuma falha do Auto-Merge Nível I encontrada.",None
    part=failure.get("partition") or _analyze_merge_partition(ch)
    if not part: return False,"Não há resultado misto para validar no Nível II.",None
    resolved=part.get("resolved_segments") or []
    pending=part.get("pending_segments") or []
    if not resolved: return False,"Nenhum trecho automático aproveitável foi encontrado.",part
    manga=ch.parent.parent
    dest=l2dir(manga,ch.name); dest.mkdir(parents=True,exist_ok=True)
    for old in dest.glob("passed-*.png"): old.unlink()
    part["level2_validated"]=True
    part["status"]="partial" if pending else "validated"
    by_id={int(seg["id"]):seg for seg in part.get("segments") or []}
    artifacts=[]
    for seg in resolved:
        seg["status"]="passed"; seg["validation"]="auto"; seg["validated_ok"]=True
        if int(seg["id"]) in by_id:
            by_id[int(seg["id"])].update({"status":"passed","validation":"auto","validated_ok":True})
        out_name=f"passed-{int(seg['id']):03d}.png"
        out_path=dest/out_name
        width=None
        canvas=Image.new("RGB",(1,1),"white")
        for span in seg.get("source_spans") or []:
            src=ch/span["file"]
            with Image.open(src) as im:
                if width is None:
                    width=im.width
                    canvas=Image.new("RGB",(width,int(seg["height"])),"white")
                crop=im.convert("RGB").crop((0,int(span["source_y_start"]),width,int(span["source_y_end"])))
                canvas.paste(crop,(0,int(span["global_start"])-int(seg["global_start"])+int(span["source_y_start"])))
        canvas.save(out_path,"PNG")
        seg["artifact"]={"file":out_name,"path":str(out_path),"storage":"MERGE_LEVEL2"}
        if int(seg["id"]) in by_id: by_id[int(seg["id"])]["artifact"]=dict(seg["artifact"])
        artifacts.append({"segment_id":int(seg["id"]),"file":out_name,"global_start":int(seg["global_start"]),"global_end":int(seg["global_end"]),"sources":seg.get("sources") or [],"validation":"auto","validated_ok":True})
    for seg in pending:
        seg["status"]="failed"; seg["validation"]="review_required"
        if int(seg["id"]) in by_id:
            by_id[int(seg["id"])].update({"status":"failed","validation":"review_required"})
    part["segments"]=[by_id[int(seg["id"])] for seg in part.get("segments") or []]
    part["resolved_segments"]=[seg for seg in part["segments"] if seg.get("status")=="passed"]
    part["pending_segments"]=[seg for seg in part["segments"] if seg.get("status")=="failed"]
    manifest={"schema_version":1,"algorithm":"merge_level2_auto_segments","chapter":ch.name,"source_dir":str(ch),"output_dir":str(dest),"total_height":int(part.get("total_height") or 0),"segments":part["resolved_segments"],"artifacts":artifacts,"pending_segments":part["pending_segments"],"coverage":{"auto_segments":[[int(s["global_start"]),int(s["global_end"])] for s in part["resolved_segments"]]}}
    (dest/"merge-level2-manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    failure["partition"]=part
    failure["level2_status"]="validated"
    failure["status"]="partial" if pending else "validated"
    p=merge_status_file(ch); p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(failure,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return True,f"Nível II validou {len(resolved)} trecho(s) automático(s); {len(pending)} segue(m) para revisão.",part

def catalog():
    out={}
    for provider in ("comix","mangago"):
        p=OUTPUT/provider
        out[provider]=sorted([x.name for x in p.iterdir() if x.is_dir() and (x/"IMG").is_dir()],key=nkey) if p.is_dir() else []
    return out




def review_merge_items(manga, ch):
    rd=rdir(manga,ch.name); mf=rd/"merge-review.json"
    if not mf.is_file(): return []
    try:
        payload=json.loads(mf.read_text(encoding="utf-8"))
        boundaries=[int(x) for x in (payload.get("boundaries") or [])]
        outputs=sorted(rd.glob("merged-*.png"),key=nkey)
        policy=payload.get("policy") or {}
        try: max_sources=int(policy.get("max_source_images") or 8)
        except (TypeError,ValueError): max_sources=8
        max_sources=max(2,min(50,max_sources))
        if len(boundaries)!=len(outputs)+1:
            return [{"file":p.name,"index":i+1,"sources":[],"source_spans":[],"analysis_sources":[],"analysis_limit":max_sources,"needs_review":True,"review_reasons":["mapeamento_incompleto"]} for i,p in enumerate(outputs)]

        source_names=payload.get("source_pages") or []
        source_dir=manga/"IMG"/ch.name
        spans=[]; y=0
        from PIL import Image
        for source_index,name in enumerate(source_names):
            p=source_dir/name
            if not p.is_file(): continue
            with Image.open(p) as im: h=int(im.height)
            spans.append({"file":name,"source_index":source_index,"global_start":y,"global_end":y+h,"height":h}); y+=h

        failure=read_merge_failure(ch) or {}
        partition=failure.get("partition") or {}
        pending_intervals=[(int(x["global_start"]),int(x["global_end"])) for x in (partition.get("pending_segments") or []) if x.get("global_start") is not None and x.get("global_end") is not None]

        review_centers=set()
        for cut in (payload.get("cuts") or []):
            if cut.get("review_strategy"):
                try: review_centers.add(int(cut["center"]))
                except Exception: pass
        for item in (payload.get("proposal") or []):
            try: review_centers.add(int(item["center"]))
            except Exception: pass

        items=[]
        for i,out in enumerate(outputs):
            start,end=boundaries[i],boundaries[i+1]
            source_spans=[]
            for sp in spans:
                a,b=sp["global_start"],sp["global_end"]
                lo,hi=max(start,a),min(end,b)
                if hi<=lo: continue
                source_spans.append({"file":sp["file"],"source_index":sp["source_index"],"merge_start":lo-start,"merge_end":hi-start,"source_start":lo-a,"source_end":hi-a,"source_height":sp["height"]})
            included={x["source_index"] for x in source_spans}
            first=source_spans[0]["source_index"] if source_spans else 0
            window=[sp for sp in spans if first<=sp["source_index"]<first+max_sources]
            analysis=[{"file":sp["file"],"source_index":sp["source_index"],"included":sp["source_index"] in included,"height":sp["height"]} for sp in window]
            reasons=[]
            if any(min(end,b)>max(start,a) for a,b in pending_intervals): reasons.append("auto_merge_pending_interval")
            if not pending_intervals and (start in review_centers or end in review_centers): reasons.append("review_cut_boundary")
            items.append({"file":out.name,"index":i+1,"global_start":start,"global_end":end,"sources":[x["file"] for x in source_spans],"source_spans":source_spans,"analysis_sources":analysis,"analysis_limit":max_sources,"included_count":sum(1 for x in analysis if x["included"]),"context_count":sum(1 for x in analysis if not x["included"]),"needs_review":bool(reasons),"review_reasons":reasons})
        has_scope=bool(pending_intervals or review_centers)
        scoped=[x for x in items if x["needs_review"]]
        return scoped if has_scope and scoped else items
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
    merge_ok=False; merge_error=None
    try: merge_ok=bool(is_chapter_merged(ch))
    except Exception as exc: merge_error=str(exc)
    failure=read_merge_failure(ch); merge_failed=bool(failure)
    partition=(failure or {}).get("partition")
    has_level2=bool(partition and (partition.get("resolved_segments") or []) and (partition.get("pending_segments") or []))
    level2_validated=bool(partition and partition.get("level2_validated"))
    needs_review=bool(merge_failed and (not has_level2 or level2_validated))
    review_items=review_merge_items(manga,ch)
    all_review_files=[p.name for p in sorted(rd.glob("merged-*.png"),key=nkey)] if rd.is_dir() else []
    visible=[x.get("file") for x in review_items if x.get("file")]
    review_exists=(rd/"merge-review.json").is_file()
    return {
        "chapter":ch.name,
        "pages":sum(1 for p in ch.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTS and p.name.lower().startswith("page-")),
        "merge":merge_ok,"merge_error":merge_error,"merge_failed":merge_failed,
        "merge_failure":failure,"merge_partition":partition,
        "merge_level2":has_level2,"merge_level2_validated":level2_validated,
        "needs_review":needs_review,
        "merge_state":"concluido" if merge_ok else ("pendente_review" if needs_review else ("parcial" if has_level2 else ("pendente_review" if merge_failed else "novo"))),
        "merged_images":len(list(md.glob("merged-*.png"))) if md.is_dir() else 0,
        "review":review_exists,
        "review_images":len(review_items) if review_exists else 0,
        "review_total_images":len(all_review_files),
        "review_auto_resolved_images":max(0,len(all_review_files)-len(visible)) if review_exists else 0,
        "review_files":visible if review_exists else [],
        "review_merges":review_items,
        "review_max_source_images":review_max_source_images(rd),
        "clean":(cdir(manga,ch.name)/"clean-manifest.json").is_file(),
        "pdf":(manga/"PDF"/ch.name/f"{ch.name}.pdf").is_file(),
        "pdf_merge":(pmdir(manga,ch.name)/f"{ch.name}.pdf").is_file(),
    }

def state(provider,manga_name):
    manga=manga_path(provider,manga_name); rows=[row_state(manga,ch) for ch in chapters(manga)]
    return {"provider":provider,"manga":manga_name,"chapters":rows,"summary":{
        "chapters":len(rows),"merges":sum(x["merge"] for x in rows),
        "pending":sum(x["merge_state"]=="pendente_review" for x in rows),
        "new":sum(x["merge_state"]=="novo" for x in rows),
        "partial":sum(x["merge_state"]=="parcial" for x in rows),
        "merge_failed":sum(x["merge_failed"] for x in rows),
        "review_pending":sum(x["needs_review"] for x in rows),
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
            elif job.action=="merge_level2": job.result=do_merge_level2(job,chs)
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

def do_merge_level2(job,chs):
    out=[]
    for i,ch in enumerate(chs,1):
        job.message=f"Auto-Merge Nível II: capítulo {ch.name}..."
        ok,msg,part=validate_merge_level2(ch)
        out.append({
            "chapter":ch.name,
            "status":"ok" if ok else "error",
            "message":msg,
            "resolved_segments":len((part or {}).get("resolved_segments") or []),
            "pending_segments":len((part or {}).get("pending_segments") or []),
        })
        job.progress=i
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
        failure=read_merge_failure(ch) or {}
        partition=failure.get("partition") or {}
        level2_validated=bool(
            failure.get("level2_status")=="validated"
            or partition.get("level2_validated")
        )
        pending_segments=(
            partition.get("pending_segments") or None
            if level2_validated
            else None
        )
        try:
            ok,msg,dest=rv.generate_candidate(
                manga,
                ch,
                max_source_images=limit,
                pending_segments=pending_segments,
            )
        except rv.ReviewSourceLimitError as exc:
            item=exc.as_dict()
            item["chapter"]=ch.name
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
