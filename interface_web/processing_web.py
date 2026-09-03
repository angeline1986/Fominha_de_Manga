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

from processamento.unificacao_imagens import image_stitcher as v3
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

def rdir(m,c): return m/"FLUXO_SECUNDARIO"/"01_MERGE_PROCESSAMENTO"/"MERGE_REVIEW"/c
def amdir(m,c): return m/"FLUXO_SECUNDARIO"/"01_MERGE_PROCESSAMENTO"/"AUTO_MERGE"/c
def l2dir(m,c): return m/"FLUXO_SECUNDARIO"/"01_MERGE_PROCESSAMENTO"/"MERGE_LEVEL2"/c
def l3dir(m,c): return m/"FLUXO_SECUNDARIO"/"01_MERGE_PROCESSAMENTO"/"MERGE_LEVEL3"/c
def cdir(m,c): return m/"FLUXO_SECUNDARIO"/"04_TEXTO_OFF"/"ORIGINAL"/c
def tmdir(m,c): return m/"FLUXO_SECUNDARIO"/"04_TEXTO_OFF"/"MERGED"/c
def pmdir(m,c): return m/"FLUXO_SECUNDARIO"/"03_PDF_MERGE"/c
def merge_status_file(ch): return ch.parent.parent/"FLUXO_SECUNDARIO"/"01_MERGE_PROCESSAMENTO"/"MERGE_STATUS"/ch.name/"merge-attempt.json"


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

def read_merge_failure(ch, analyze_missing=True):
    p=merge_status_file(ch)
    if not p.is_file(): return None
    try:
        payload=json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"schema_version":1,"chapter":ch.name,"status":"error","message":"Falha de merge não legível."}
    part_payload=payload.get("partition") or {}
    if analyze_missing and (not payload.get("partition") or int(part_payload.get("schema_version") or 0)<2):
        part=_analyze_merge_partition(ch)
        if part:
            payload["partition"]=part
            try: p.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
            except Exception as exc: print(f"[processing-web] Não foi possível persistir partição do cap {ch.name}: {exc}")
    return payload

def _materialize_level1_resolved(ch, part):
    # Persiste imediatamente os segmentos PASSED produzidos pelo Auto-Merge Nível I.
    from PIL import Image
    from processamento.unificacao_imagens import image_stitcher as v3

    resolved = part.get("resolved_segments") or []
    if not resolved:
        return []

    manga = ch.parent.parent
    dest = amdir(manga, ch.name)
    dest.mkdir(parents=True, exist_ok=True)

    for old in dest.glob("*.png"):
        if (
            v3.PAGE_RANGE_OUTPUT_RE.match(old.name)
            or re.match(r"^auto-\d+\.png$", old.name, re.IGNORECASE)
        ):
            old.unlink()

    artifacts = []
    by_id = {int(seg["id"]): seg for seg in part.get("segments") or []}
    for seg in resolved:
        out_name = v3.page_range_output_name_from_spans(
            seg.get("source_spans") or [],
            int(seg["global_start"]),
            int(seg["global_end"]),
        )
        out_path = v3.ensure_unique_output_path(dest, out_name)
        width = None
        canvas = Image.new("RGB", (1, 1), "white")
        for span in seg.get("source_spans") or []:
            src = ch / span["file"]
            with Image.open(src) as im:
                if width is None:
                    width = im.width
                    canvas = Image.new("RGB", (width, int(seg["height"])), "white")
                crop = im.convert("RGB").crop(
                    (0, int(span["source_y_start"]), width, int(span["source_y_end"]))
                )
                canvas.paste(
                    crop,
                    (
                        0,
                        int(span["global_start"])
                        - int(seg["global_start"])
                        + int(span["source_y_start"]),
                    ),
                )
        canvas.save(out_path, "PNG")
        artifact = {"file": out_name, "path": str(out_path), "storage": "AUTO_MERGE"}
        seg["artifact"] = artifact
        if int(seg["id"]) in by_id:
            by_id[int(seg["id"])]["artifact"] = dict(artifact)
        artifacts.append({
            "segment_id": int(seg["id"]),
            "file": out_name,
            "global_start": int(seg["global_start"]),
            "global_end": int(seg["global_end"]),
            "sources": seg.get("sources") or [],
            "validation": "auto",
            "validated_ok": True,
        })

    manifest = {
        "schema_version": 1,
        "algorithm": "auto_merge_level1_resolved_segments",
        "chapter": ch.name,
        "source_dir": str(ch),
        "output_dir": str(dest),
        "total_height": int(part.get("total_height") or 0),
        "artifacts": artifacts,
        "pending_segments": part.get("pending_segments") or [],
        "coverage": {
            "auto_segments": [
                [int(s["global_start"]), int(s["global_end"])]
                for s in resolved
            ]
        },
    }
    (dest / "auto-merge-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return artifacts


def set_merge_failure(ch,message):
    p=merge_status_file(ch); p.parent.mkdir(parents=True,exist_ok=True)
    payload={"schema_version":2,"chapter":ch.name,"status":"error","message":str(message)}
    part=_analyze_merge_partition(ch)
    if part:
        artifacts=_materialize_level1_resolved(ch,part)
        payload["partition"]=part
        payload["auto_merge_level1"]={
            "storage":"AUTO_MERGE",
            "artifacts_count":len(artifacts),
            "output_dir":str(amdir(ch.parent.parent,ch.name)),
        }
    p.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")

def clear_merge_failure(ch):
    p=merge_status_file(ch)
    if p.is_file(): p.unlink()
    if p.parent.is_dir() and not any(p.parent.iterdir()): p.parent.rmdir()


def _load_stage_manifest(path, algorithm, label):
    if not path.is_file():
        return None, f"Manifesto {label} não encontrado: {path}"
    try:
        payload=json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, f"Manifesto {label} inválido: {exc}"
    if payload.get("algorithm") != algorithm:
        return None, f"Manifesto {label} possui algoritmo não suportado."
    return payload, None

def _stage_artifact_pieces(directory, payload, key, stage):
    pieces=[]
    for artifact in payload.get(key) or []:
        pieces.append({
            "global_start":int(artifact["global_start"]),
            "global_end":int(artifact["global_end"]),
            "source":directory/str(artifact["file"]),
            "source_file":str(artifact["file"]),
            "source_stage":stage,
        })
    return pieces

def _promote_stage_composition(ch, pieces, total_height, algorithm, composition):
    from datetime import datetime, timezone
    from PIL import Image
    from processamento.unificacao_imagens import image_stitcher as v3
    if total_height <= 0 or not pieces:
        return False, "Composição final sem cobertura válida."
    pieces=sorted(pieces,key=lambda x:(x["global_start"],x["global_end"],x["source_stage"],x["source_file"]))
    expected=0; expected_width=None
    for piece in pieces:
        start=int(piece["global_start"]); end=int(piece["global_end"]); source=piece["source"]
        if start != expected:
            relation="lacuna" if start>expected else "sobreposição"
            return False,f"Cobertura final inválida ({relation}): esperado {expected}, encontrado {start}."
        if end<=start or not source.is_file():
            return False,f"Artefato inválido/ausente na composição: {source}."
        try:
            with Image.open(source) as im:
                width=int(im.width); height=int(im.height)
        except Exception as exc:
            return False,f"Artefato ilegível {source.name}: {exc}"
        if height != end-start:
            return False,f"Altura incompatível em {source.name}: {height} != {end-start}."
        if expected_width is None: expected_width=width
        elif width != expected_width: return False,f"Largura incompatível em {source.name}: {width} != {expected_width}."
        expected=end
    if expected != int(total_height):
        return False,f"Cobertura final incompleta: {expected} != {total_height}."
    official=v3.merge_output_dir(ch)
    if official.exists():
        if v3.is_chapter_merged(ch): return False,"Já existe MERGE oficial válido para este capítulo."
        return False,"Já existe MERGE oficial não reconhecido; promoção cancelada por segurança."
    official.mkdir(parents=True,exist_ok=False)
    outputs=[]
    try:
        for piece in pieces:
            dest=v3.ensure_unique_output_path(official,piece["source"].name)
            shutil.copy2(piece["source"],dest)
            outputs.append({"file":dest.name,"global_start":piece["global_start"],"global_end":piece["global_end"],"width":expected_width,"height":piece["global_end"]-piece["global_start"],"sources":[],"source_stage":piece["source_stage"],"source_file":piece["source_file"]})
        manifest={"schema_version":1,"algorithm":algorithm,"status":"approved","approved_at":datetime.now(timezone.utc).isoformat(),"source_dir":str(ch),"output_dir":str(official),"source_width":int(expected_width or 0),"source_total_height":int(total_height),"merged_images":len(outputs),"outputs":outputs,"validation":{"ok":True,"errors":[],"coverage_start":0,"coverage_end":int(total_height)},"safety":{"source_files_modified":False,"forced_cut_without_white_band":False,"all_source_pixels_preserved_in_order":True,"stage_artifacts_rerendered":False},"composition":composition}
        (official/"merge-manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        if not v3.is_chapter_merged(ch): raise RuntimeError("MERGE consolidado não foi reconhecido após a promoção.")
    except Exception as exc:
        if official.is_dir(): shutil.rmtree(official)
        return False,f"Falha ao consolidar MERGE: {exc}"
    return True,f"Composição final promovida para {official}"

def _promote_level1_complete(ch):
    manga=ch.parent.parent; auto_dir=amdir(manga,ch.name); mp=auto_dir/"auto-merge-manifest.json"
    payload,err=_load_stage_manifest(mp,"auto_merge_level1_complete","Auto-Merge")
    if err: return False,err
    pieces=_stage_artifact_pieces(auto_dir,payload,"artifacts","auto_merge")
    return _promote_stage_composition(ch,pieces,int(payload.get("total_height") or 0),"merge_auto_level1_composition_v1",{"auto_merge_manifest":"auto-merge-manifest.json","level2_manifest":None,"level3_manifest":None,"review_manifest":None,"scope":"level1_complete"})

def _promote_level2_complete(ch, part):
    manga=ch.parent.parent; auto_dir=amdir(manga,ch.name); level2_dir=l2dir(manga,ch.name)
    auto,err=_load_stage_manifest(auto_dir/"auto-merge-manifest.json","auto_merge_level1_resolved_segments","Auto-Merge")
    if err: return False,err
    l2,err=_load_stage_manifest(level2_dir/"merge-level2-manifest.json","merge_level2_bounded_safe_path_v1","Level II")
    if err: return False,err
    if l2.get("pending_segments"): return False,"Level II ainda possui segmentos pendentes; promoção direta cancelada."
    pieces=_stage_artifact_pieces(auto_dir,auto,"artifacts","auto_merge")+_stage_artifact_pieces(level2_dir,l2,"artifacts","level2")
    return _promote_stage_composition(ch,pieces,int(l2.get("total_height") or auto.get("total_height") or 0),"merge_auto_level2_composition_v2",{"auto_merge_manifest":"auto-merge-manifest.json","level2_manifest":"merge-level2-manifest.json","level3_manifest":None,"review_manifest":None,"scope":"level2_complete"})

def _promote_level3_complete(ch, part=None):
    import hashlib
    manga=ch.parent.parent; auto_dir=amdir(manga,ch.name); level2_dir=l2dir(manga,ch.name); level3_dir=l3dir(manga,ch.name)
    auto,err=_load_stage_manifest(auto_dir/"auto-merge-manifest.json","auto_merge_level1_resolved_segments","Auto-Merge")
    if err: return False,err
    l2_path=level2_dir/"merge-level2-manifest.json"; l2,err=_load_stage_manifest(l2_path,"merge_level2_bounded_safe_path_v1","Level II")
    if err: return False,err
    l3,err=_load_stage_manifest(level3_dir/"merge-level3-manifest.json","merge_level3_structural_safe_v1","Level III")
    if err: return False,err
    if str(l3.get("source_level2_sha256") or "") != hashlib.sha256(l2_path.read_bytes()).hexdigest(): return False,"Manifesto Level III está desatualizado em relação ao Level II; promoção direta cancelada."
    if l3.get("residual_pending_segments"): return False,"Level III ainda possui residual pendente; promoção direta cancelada."
    pieces=_stage_artifact_pieces(auto_dir,auto,"artifacts","auto_merge")+_stage_artifact_pieces(level2_dir,l2,"artifacts","level2")+_stage_artifact_pieces(level3_dir,l3,"safe_artifacts","level3")
    return _promote_stage_composition(ch,pieces,int(l2.get("total_height") or 0),"merge_auto_level2_level3_composition_v2",{"auto_merge_manifest":"auto-merge-manifest.json","level2_manifest":"merge-level2-manifest.json","level3_manifest":"merge-level3-manifest.json","review_manifest":None,"scope":"level3_all_safe"})


def _materialize_level3_interval(ch, segment):
    from PIL import Image
    spans=segment.get("source_spans") or []
    if not spans: raise ValueError("Segmento Level III sem source_spans.")
    start=int(segment["global_start"]); end=int(segment["global_end"])
    if end<=start: raise ValueError("Intervalo Level III inválido.")
    width=None; canvas=None
    for span in spans:
        src=ch/span["file"]
        if not src.is_file(): raise FileNotFoundError(f"Fonte ausente: {span['file']}")
        with Image.open(src) as im:
            if width is None:
                width=int(im.width); canvas=Image.new("RGB",(width,end-start),"white")
            elif int(im.width)!=width:
                raise ValueError("Larguras incompatíveis no Level III.")
            sy0=int(span["source_y_start"]); sy1=int(span["source_y_end"])
            crop=im.convert("RGB").crop((0,sy0,width,sy1))
            paste_y=int(span["global_start"])-start+sy0
            canvas.paste(crop,(0,paste_y))
    if canvas is None: raise ValueError("Falha ao materializar Level III.")
    return canvas


def process_merge_level3_pending(ch, part):
    # Executa somente sobre FAILED de um Level II já validado.
    import numpy as np
    from processamento.unificacao_imagens import image_stitcher as v3
    from processamento.unificacao_imagens.image_stitcher_level3 import (
        Level3Config, Level3Decision, Level3PendingRegion,
        continuous_scene_guard, search_local_safe_candidate,
    )
    if not part or not part.get("level2_validated"):
        return False,"Level III exige Level II validado.",None
    pending=part.get("pending_segments") or []
    if not pending:
        return False,"Level II não possui FAILED para Level III.",None

    manga=ch.parent.parent
    dest=l3dir(manga,ch.name); dest.mkdir(parents=True,exist_ok=True)
    for old in dest.glob("*.png"):
        if (
            v3.PAGE_RANGE_OUTPUT_RE.match(old.name)
            or re.match(r"^safe-\d+\.png$", old.name, re.IGNORECASE)
        ):
            old.unlink()

    cfg=Level3Config(); artifacts=[]; residual=[]; diagnostics=[]; out_index=1
    max_h=int(v3.DEFAULT_MAX_CHUNK_HEIGHT)

    for seg in pending:
        seg_start=int(seg["global_start"]); seg_end=int(seg["global_end"])
        image=_materialize_level3_interval(ch,seg)
        gray=np.asarray(image.convert("L"),dtype=np.uint8)
        region=Level3PendingRegion(seg_start,seg_end)
        cursor=seg_start; proven=[]

        while seg_end-cursor>max_h:
            nominal=cursor+max_h
            result=search_local_safe_candidate(
                gray,candidate_y=nominal,region=region,
                image_global_start=seg_start,config=cfg,
            )
            chosen=None
            if result.decision==Level3Decision.SAFE:
                chosen=int(result.alternative_y if result.alternative_y is not None else result.candidate_y)
            diagnostics.append({
                **result.as_dict(),"segment_id":int(seg["id"]),
                "nominal_candidate_y":nominal,"selected_y":chosen,
            })
            if chosen is None or chosen<=cursor or chosen>=seg_end:
                guard=continuous_scene_guard(
                    region=Level3PendingRegion(cursor,seg_end),config=cfg
                )
                residual.append({
                    **seg,"global_start":cursor,"global_end":seg_end,
                    "height":seg_end-cursor,"status":"failed",
                    "validation":"review_required",
                    "reason":guard.reason if guard is not None else result.reason,
                    "level3_decision":result.decision.value,
                    # MIII-4A: preserve both the structural rejection that
                    # triggered the stop and the independent flow guard that
                    # ultimately routed the residual to Review.
                    "trigger_reason":result.reason,
                    "trigger_decision":result.decision.value,
                    "guard_metrics":dict(guard.metrics) if guard is not None else {},
                })
                break
            proven.append((cursor,chosen,result.reason))
            cursor=chosen
        else:
            if cursor<seg_end:
                proven.append((cursor,seg_end,"remaining_within_max_height"))

        for start,end,reason in proven:
            crop=image.crop((0,start-seg_start,image.width,end-seg_start))
            name=v3.page_range_output_name_from_spans(
                seg.get("source_spans") or [], start, end
            )
            path=v3.ensure_unique_output_path(dest,name)
            crop.save(path,"PNG")
            artifacts.append({
                "file":name,"global_start":start,"global_end":end,
                "height":end-start,"source_stage":"level3",
                "source_segment_id":int(seg["id"]),"decision_reason":reason,
            })
            out_index+=1

    level2_manifest_path=l2dir(manga,ch.name)/"merge-level2-manifest.json"
    if not level2_manifest_path.is_file():
        return False,"Manifesto Level II ausente ao finalizar Level III.",None
    import hashlib
    level2_sha256=hashlib.sha256(level2_manifest_path.read_bytes()).hexdigest()

    manifest={
        "schema_version":1,"algorithm":"merge_level3_structural_safe_v1",
        "chapter":ch.name,"source_dir":str(ch),"output_dir":str(dest),
        "total_height":int(part.get("total_height") or 0),
        "source_level2_manifest":"merge-level2-manifest.json",
        "source_level2_sha256":level2_sha256,
        "safe_artifacts":artifacts,"residual_pending_segments":residual,
        "diagnostics":diagnostics,
        "safety":{"level2_passed_artifacts_modified":False,
                  "forced_cut":False,
                  "inconclusive_local_search_allowed":False},
    }
    (dest/"merge-level3-manifest.json").write_text(
        json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"
    )
    return True,(
        f"Level III materializou {len(artifacts)} trecho(s) SAFE; "
        f"{len(residual)} residual(is) segue(m) para Review."
    ),manifest


def _materialize_level2_piece(ch, infos, start, end, dest, source_segment_id, reason):
    from PIL import Image
    spans=_segment_bounds(infos,start,end)
    if not spans: raise ValueError("Intervalo Level II sem source_spans.")
    width=None; canvas=None
    for span in spans:
        src=ch/span["file"]
        if not src.is_file(): raise FileNotFoundError(f"Fonte ausente no Level II: {span['file']}")
        with Image.open(src) as im:
            if width is None:
                width=int(im.width); canvas=Image.new("RGB",(width,end-start),"white")
            elif int(im.width)!=width:
                raise ValueError("Larguras incompatíveis no Level II.")
            sy0=int(span["source_y_start"]); sy1=int(span["source_y_end"])
            crop=im.convert("RGB").crop((0,sy0,width,sy1))
            paste_y=int(span["global_start"])-int(start)+sy0
            canvas.paste(crop,(0,paste_y))
    if canvas is None: raise ValueError("Falha ao materializar trecho Level II.")
    name=v3.page_range_output_name_from_spans(spans,start,end)
    path=v3.ensure_unique_output_path(dest,name)
    canvas.save(path,"PNG")
    return {
        "file":name,"global_start":int(start),"global_end":int(end),
        "height":int(end-start),"sources":[x["file"] for x in spans],
        "source_spans":spans,"source_stage":"level2",
        "source_segment_id":int(source_segment_id),"decision_reason":reason,
        "validation":"auto","validated_ok":True,
    }


def _level2_residual_segment(parent,start,end,infos):
    item=dict(parent); spans=_segment_bounds(infos,start,end)
    item.update({
        "global_start":int(start),"global_end":int(end),"height":int(end-start),
        "sources":[x["file"] for x in spans],"source_spans":spans,
        "label":_page_range_label(spans),"status":"failed",
        "validation":"review_required","reason":"level2_no_complete_safe_path",
    })
    item.pop("artifact",None)
    return item


def validate_merge_level2(ch):
    """Executa busca segura própria do Level II somente sobre o residual do Level I.

    Mantém os thresholds de faixa branca do V3 e nunca força cortes. A capacidade
    adicional vem de procurar um caminho seguro em toda a janela viável do
    residual, em vez de limitar a busca à janela-alvo usada pelo Level I.
    """
    from processamento.unificacao_imagens.image_stitcher_level2 import (
        Level2Config, analyze_uniform_color_bands, solve_pending_region,
    )
    failure=read_merge_failure(ch)
    if not failure: return False,"Nenhuma falha do Auto-Merge Nível I encontrada.",None
    part=failure.get("partition") or _analyze_merge_partition(ch)
    if not part: return False,"Não há residual do Auto-Merge Nível I para o Nível II.",None
    manga=ch.parent.parent; auto_path=amdir(manga,ch.name)/"auto-merge-manifest.json"
    auto,err=_load_stage_manifest(auto_path,"auto_merge_level1_resolved_segments","Auto-Merge")
    if err: return False,err,part
    pending=[dict(x) for x in (auto.get("pending_segments") or [])]
    pages=v3.list_pages(ch)
    if not pages: return False,"Nenhuma imagem-fonte encontrada para o Nível II.",part
    infos,bands,total_height,_=v3.analyze_chapter(
        pages,sample_width=v3.DEFAULT_SAMPLE_WIDTH,
        light_threshold=v3.DEFAULT_LIGHT_THRESHOLD,
        white_ratio_threshold=v3.DEFAULT_WHITE_RATIO,
    )
    expected_total=int(auto.get("total_height") or part.get("total_height") or 0)
    if int(total_height)!=expected_total or expected_total<=0:
        return False,"Total do capítulo diverge do manifesto Auto-Merge; Nível II cancelado.",part
    dest=l2dir(manga,ch.name); dest.mkdir(parents=True,exist_ok=True)
    for old in dest.glob("*.png"):
        if v3.PAGE_RANGE_OUTPUT_RE.match(old.name) or re.match(r"^(?:passed|level2)-\d+\.png$",old.name,re.IGNORECASE): old.unlink()
    cfg=Level2Config(); artifacts=[]; residual=[]; diagnostics=[]
    uniform_bands=analyze_uniform_color_bands(
        pages,
        sample_width=v3.DEFAULT_SAMPLE_WIDTH,
        max_channel_std=cfg.uniform_max_channel_std,
        max_row_delta=cfg.uniform_max_row_delta,
    )
    level2_candidates=list(bands)+list(uniform_bands)
    source_intervals=[(int(info.global_start),int(info.global_end)) for info in infos]
    for seg in pending:
        start=int(seg["global_start"]); end=int(seg["global_end"])
        plan=solve_pending_region(
            start,end,level2_candidates,cfg,source_intervals=source_intervals
        )
        diagnostics.append({"segment_id":int(seg.get("id") or seg.get("index") or 0),"global_start":start,"global_end":end,**plan})
        selected_types={str(x.get("candidate_type") or "white_band") for x in (plan.get("selected_cuts") or [])}
        if plan.get("edge_chunk_relaxation_used"):
            decision_reason="level2_safe_edge_chunk_last_fallback"
        elif "uniform_color_band" in selected_types:
            decision_reason="level2_safe_uniform_color_balanced_path"
        else:
            decision_reason="level2_safe_white_balanced_path"
        for a,b in plan.get("resolved_intervals") or []:
            artifacts.append(_materialize_level2_piece(
                ch,infos,int(a),int(b),dest,
                int(seg.get("id") or seg.get("index") or 0),
                decision_reason,
            ))
        residual_interval=plan.get("residual_interval")
        if residual_interval:
            residual.append(_level2_residual_segment(seg,int(residual_interval[0]),int(residual_interval[1]),infos))
    manifest={
        "schema_version":3,"algorithm":"merge_level2_bounded_safe_path_v1",
        "chapter":ch.name,"source_dir":str(ch),"output_dir":str(dest),
        "total_height":expected_total,"source_auto_merge_manifest":"auto-merge-manifest.json",
        "artifacts":artifacts,"pending_segments":residual,
        "coverage":{"level2_segments":[[int(x["global_start"]),int(x["global_end"])] for x in artifacts]},
        "diagnostics":diagnostics,
        "policy":{
            "target_height":int(cfg.target_height),
            "min_chunk_height":int(cfg.min_chunk_height),
            "min_chunk_height_semantics":"preferred_for_internal_chunks",
            "edge_chunk_below_min_allowed":True,
            "edge_chunk_scope":"residual_start_or_end_only",
            "max_chunk_height":int(cfg.max_chunk_height),
            "min_white_band":int(cfg.min_white_band),
            "white_ratio_threshold":float(v3.DEFAULT_WHITE_RATIO),
            "light_threshold":int(v3.DEFAULT_LIGHT_THRESHOLD),
            "uniform_color_enabled":True,
            "uniform_color_is_color_agnostic":True,
            "min_uniform_band":int(cfg.min_uniform_band),
            "uniform_max_channel_std":float(cfg.uniform_max_channel_std),
            "uniform_max_row_delta":float(cfg.uniform_max_row_delta),
            "preferred_source_files_per_merge":int(cfg.preferred_source_files),
            "preferred_source_files_is_safety_rule":False,
            "balance_scoring_enabled":True,
            "edge_chunk_is_last_fallback":True,
            "strategy":"safe_white_or_uniform_color_balanced_path_with_edge_last_fallback",
        },
        "safety":{
            "level1_artifacts_duplicated":False,
            "level1_artifacts_modified":False,
            "v3_thresholds_relaxed":False,
            "edge_chunk_visual_thresholds_relaxed":False,
            "uniform_color_does_not_require_white":True,
            "uniform_color_requires_low_spatial_variation":True,
            "balance_score_never_authorizes_unsafe_candidate":True,
            "preferred_source_file_count_never_authorizes_unsafe_candidate":True,
            "forced_cut":False,
        },
    }
    (dest/"merge-level2-manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    part["level2_validated"]=True
    part["level2_resolved_segments"]=[dict(x) for x in artifacts]
    part["level2_resolved_segments_count"]=len(artifacts)
    part["pending_segments"]=residual
    part["pending_segments_count"]=len(residual)
    failure["partition"]=part; failure["level2_status"]="validated"; failure["status"]="partial" if residual else "validated"
    merge_status_file(ch).write_text(json.dumps(failure,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    if not residual:
        promoted,msg=_promote_level2_complete(ch,part)
        if promoted: clear_merge_failure(ch)
        return promoted,msg,part
    if artifacts:
        edge_regions=sum(1 for item in diagnostics if item.get("edge_chunk_relaxation_used"))
        edge_note=(f" {edge_regions} região(ões) usou(aram) edge chunk seguro na borda do residual." if edge_regions else "")
        return True,f"Nível II resolveu {len(artifacts)} trecho(s) novo(s) com busca segura.{edge_note} {len(residual)} residual(is) permanece(m) pendente(s).",part
    return True,f"Nível II analisou {len(pending)} residual(is), mas não encontrou caminho adicional de cortes seguros; {len(residual)} residual(is) permanece(m) pendente(s).",part

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
        outputs=v3.merge_artifact_files(rd)
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
        pending_segments=partition.get("pending_segments") or []

        if _is_level2_validated(failure):
            authoritative_pending,pending_error,pending_source=_level3_review_pending(ch,failure)
            if pending_error:
                print(
                    f"[processing-web] Review cap {ch.name} bloqueada: "
                    f"{pending_error}"
                )
                return []
            if pending_source=="level3":
                if not authoritative_pending:
                    return []
                pending_segments=authoritative_pending
            elif pending_source=="level2":
                pending_segments=authoritative_pending or []
            elif pending_source=="level3_pending":
                return []

        pending_intervals=[(int(x["global_start"]),int(x["global_end"])) for x in pending_segments if x.get("global_start") is not None and x.get("global_end") is not None]

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
        folder=manga/"FLUXO_SECUNDARIO"/"03_PDF_MERGE"/str(chapter)
        if not folder.is_dir():
            return []
        return [p.name for p in sorted(folder.glob("*.pdf"), key=nkey) if p.is_file()]
    except Exception:
        return []


def latest_pdf_merge_batch(manga):
    root = manga / "FLUXO_SECUNDARIO" / "03_PDF_MERGE"
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


def _merge_manifest_state(ch):
    """Lê somente metadados do MERGE oficial para compor /api/state.

    Não abre pixels, não recalcula merge e não executa validação profunda.
    """
    md=v3.merge_output_dir(ch)
    manifest_path=md/"merge-manifest.json"
    result={"ok":False,"merged_images":0,"error":None}
    if not manifest_path.is_file():
        return result
    try:
        payload=json.loads(manifest_path.read_text(encoding="utf-8"))
        validation=payload.get("validation") or {}
        outputs=payload.get("outputs")
        total_height=int(payload.get("source_total_height") or 0)
        merged_images=int(payload.get("merged_images") or 0)
        coverage_start=int(validation.get("coverage_start"))
        coverage_end=int(validation.get("coverage_end"))
    except Exception as exc:
        result["error"]=f"Manifesto MERGE inválido: {exc}"
        return result
    if validation.get("ok") is not True:
        return result
    if total_height<=0 or coverage_start!=0 or coverage_end!=total_height:
        return result
    if not isinstance(outputs,list) or not outputs or merged_images!=len(outputs):
        return result
    expected_start=0
    md_resolved=md.resolve()
    seen_files=set()
    try:
        for item in outputs:
            if not isinstance(item,dict):
                return result
            name=str(item.get("file") or "").strip()
            if not name or Path(name).name!=name or name in seen_files:
                return result
            start=int(item.get("global_start"))
            end=int(item.get("global_end"))
            if start!=expected_start or end<=start:
                return result
            output_path=(md/name).resolve()
            if not output_path.is_relative_to(md_resolved) or not output_path.is_file():
                return result
            seen_files.add(name)
            expected_start=end
    except Exception as exc:
        result["error"]=f"Metadados MERGE inválidos: {exc}"
        return result
    if expected_start!=total_height:
        return result
    result["ok"]=True
    result["merged_images"]=merged_images
    return result

def _is_level2_validated(failure):
    """Interpreta de forma única o estado persistido do Level II."""
    failure = failure or {}
    partition = failure.get("partition") or {}

    return bool(
        failure.get("level2_status") == "validated"
        or partition.get("level2_validated")
    )


def _level3_ui_detail(manga,ch,failure):
    """Expõe ao frontend somente dados de Level III validados contra o Level II atual."""
    manifest_path=l3dir(manga,ch.name)/"merge-level3-manifest.json"
    if not manifest_path.is_file():
        return None
    authoritative_pending,pending_error,pending_source=_level3_review_pending(ch,failure or {})
    if pending_source!="level3":
        return None
    if pending_error:
        return {
            "available":True,
            "valid":False,
            "error":pending_error,
        }
    try:
        payload=json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError,ValueError,TypeError,json.JSONDecodeError) as exc:
        return {
            "available":True,
            "valid":False,
            "error":f"Manifesto Level III inválido: {exc}",
        }
    safe=payload.get("safe_artifacts") or []
    residual=payload.get("residual_pending_segments") or []
    diagnostics=payload.get("diagnostics") or []
    return {
        "available":True,
        "valid":True,
        "error":None,
        "algorithm":payload.get("algorithm"),
        "total_height":int(payload.get("total_height") or 0),
        "safe_artifacts_count":len(safe),
        "residual_pending_segments_count":len(residual),
        "safe_artifacts":safe,
        "residual_pending_segments":residual,
        "diagnostics":diagnostics,
        "review_pending_segments":authoritative_pending or [],
        "safety":payload.get("safety") or {},
    }

def row_state(manga,ch):
    from processamento.unificacao_imagens.image_stitcher import merge_output_dir
    md=merge_output_dir(ch); rd=rdir(manga,ch.name)
    merge_meta=_merge_manifest_state(ch)
    merge_ok=bool(merge_meta.get("ok")); merge_error=merge_meta.get("error")
    failure=read_merge_failure(ch,analyze_missing=False); merge_failed=bool(failure)
    partition=(failure or {}).get("partition")
    has_level2_data=bool(
        partition
        and (partition.get("resolved_segments") or [])
    )
    has_level2=bool(
        has_level2_data
        and (partition.get("pending_segments") or [])
    )
    level2_validated=_is_level2_validated(failure)
    validated_without_pending=bool(
        merge_failed
        and has_level2_data
        and level2_validated
        and not (partition.get("pending_segments") or [])
    )
    level3_detail=_level3_ui_detail(manga,ch,failure)
    level3_valid=bool(
        level3_detail
        and level3_detail.get("available")
        and level3_detail.get("valid")
    )
    level3_has_residual=bool(
        level3_valid
        and (
            level3_detail.get("review_pending_segments")
            or level3_detail.get("residual_pending_segments")
        )
    )
    level3_pending=bool(
        merge_failed
        and has_level2
        and level2_validated
        and not level3_valid
    )
    needs_review=bool(
        merge_failed
        and not validated_without_pending
        and (
            (not has_level2)
            or (level2_validated and level3_has_residual)
        )
    )
    review_items=review_merge_items(manga,ch)
    all_review_files=[p.name for p in v3.merge_artifact_files(rd)] if rd.is_dir() else []
    visible=[x.get("file") for x in review_items if x.get("file")]
    review_exists=(rd/"merge-review.json").is_file()
    return {
        "chapter":ch.name,
        "pages":sum(1 for p in ch.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTS and p.name.lower().startswith("page-")),
        "merge":merge_ok,"merge_error":merge_error,"merge_failed":merge_failed,
        "merge_failure":failure,"merge_partition":partition,
        "merge_level2":has_level2,"merge_level2_validated":level2_validated,
        "merge_level3_pending":level3_pending,
        "merge_level3_detail":level3_detail,
        "needs_review":needs_review,
        "merge_state":"concluido" if merge_ok else ("pendente_level3" if level3_pending else ("pendente_review" if needs_review else ("parcial" if (has_level2 or validated_without_pending) else ("pendente_review" if merge_failed else "novo")))),
        "merged_images":int(merge_meta.get("merged_images") or 0) if merge_ok else 0,
        "review":review_exists,
        "review_images":len(review_items) if review_exists else 0,
        "review_total_images":len(all_review_files),
        "review_auto_resolved_images":max(0,len(all_review_files)-len(visible)) if review_exists else 0,
        "review_files":visible if review_exists else [],
        "review_merges":review_items,
        "review_max_source_images":review_max_source_images(rd),
        "clean":(cdir(manga,ch.name)/"clean-manifest.json").is_file(),
        "clean_merged":(tmdir(manga,ch.name)/"clean-manifest.json").is_file(),
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
        "level3_pending":sum(x.get("merge_level3_pending",False) for x in rows),
        "merge_failed":sum(x["merge_failed"] for x in rows),
        "review_pending":sum(x["needs_review"] for x in rows),
        "review":sum(x["review"] for x in rows),"pdfs":sum(x["pdf"] for x in rows),"clean":sum(x["clean"] for x in rows),
        "clean_merged":sum(x["clean_merged"] for x in rows),"pdf_merge":sum(x["pdf_merge"] for x in rows)}}

@dataclass
class Job:
    id:int; action:str; status:str="queued"; progress:int=0; total:int=0; message:str=""; error:str|None=None; result:Any=None
    progress_value:float=0.0
    progress_max:float=0.0
    progress_detail:str=""

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
            elif job.action=="clean_merged": job.result=do_clean_merged(job,manga,chs)
            elif job.action=="merge_level2": job.result=do_merge_level2(job,chs)
            elif job.action=="merge_level3": job.result=do_merge_level3(job,chs)
            elif job.action=="review_generate": job.result=do_review_generate(job,manga,chs,payload.get("max_source_images"))
            elif job.action=="review_approve": job.result=do_review_approve(job,manga,chs)
            elif job.action=="review_reject": job.result=do_review_reject(job,manga,chs)
            else: raise ValueError("Ação inválida.")
            job.status="done"; job.message="Processamento concluído."
    except Exception as e:
        job.status="error"; job.error=str(e); job.message=str(e); traceback.print_exc()


def _auto_merge_summary_payload(ch, failure=None):
    """Retorna somente metadados reais já persistidos pelo Auto-Merge para a UI."""
    auto_dir=amdir(ch.parent.parent,ch.name)
    manifest_path=auto_dir/"auto-merge-manifest.json"
    manifest={}
    if manifest_path.is_file():
        try:
            manifest=json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            manifest={}
    artifacts=manifest.get("artifacts") or []
    files=[
        str(item.get("file"))
        for item in artifacts
        if isinstance(item,dict) and item.get("file")
    ]
    failure=failure or {}
    part=failure.get("partition") or {}
    pending_segments=part.get("pending_segments") or manifest.get("pending_segments") or []
    pending_files=list(part.get("pending_source_pages") or [])
    if not pending_files:
        seen=set()
        for seg in pending_segments:
            for name in (seg.get("sources") or []):
                name=str(name)
                if name and name not in seen:
                    seen.add(name)
                    pending_files.append(name)
    residuals=[]
    reasons=[]
    for seg in pending_segments:
        try:
            start=int(seg.get("global_start"))
            end=int(seg.get("global_end"))
        except Exception:
            continue
        residuals.append({"global_start":start,"global_end":end})
        reason=str(seg.get("reason") or "")
        if reason and reason not in reasons:
            reasons.append(reason)
    return {
        "auto_merge_files":files,
        "pending_files":pending_files,
        "pending_segments_count":len(pending_segments),
        "residuals":residuals,
        "reason_codes":reasons,
    }

def do_merge(job,chs):
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from processamento.unificacao_imagens.image_stitcher import is_chapter_merged, merge_chapter
    progress_lock=threading.Lock()
    per_chapter={ch.name:0.0 for ch in chs}

    def report(ch_name,event):
        stage=str((event or {}).get("stage") or "")
        current=max(0,int((event or {}).get("current") or 0))
        total=max(1,int((event or {}).get("total") or 1))
        ratio=max(0.0,min(1.0,current/total))
        if stage=="prepare":
            chapter_ratio=0.01
        elif stage=="analyze_pages":
            chapter_ratio=0.05 + (0.70*ratio)
        elif stage=="choose_cuts":
            chapter_ratio=0.78
        elif stage=="render":
            chapter_ratio=0.82
        elif stage=="validate":
            chapter_ratio=0.97
        elif stage=="done":
            chapter_ratio=1.0
        else:
            chapter_ratio=per_chapter.get(ch_name,0.0)
        with progress_lock:
            per_chapter[ch_name]=max(per_chapter.get(ch_name,0.0),chapter_ratio)
            job.progress_value=sum(per_chapter.values())
            job.progress_max=float(max(1,len(chs)))
            pct=round((job.progress_value/job.progress_max)*100)
            detail=str((event or {}).get("message") or "")
            job.progress_detail=f"Cap. {ch_name}: {detail}" if detail else f"Cap. {ch_name}"
            job.message=f"Auto-Merge: {pct}% · {job.progress_detail}"

    def process_one(ch):
        try:
            if is_chapter_merged(ch):
                clear_merge_failure(ch)
                report(ch.name,{"stage":"done","current":1,"total":1,"message":"MERGE já existente"})
                summary=_auto_merge_summary_payload(ch)
                return {
                    "chapter":ch.name,
                    "status":"skipped",
                    "message":"MERGE já existente",
                    "auto_merge_saved":len(summary["auto_merge_files"]),
                    "auto_merge_folder":str(amdir(ch.parent.parent,ch.name)),
                    "auto_merge_files":summary["auto_merge_files"],
                    "pending_files":[],
                    "pending_segments_count":0,
                    "residuals":[],
                    "reason_codes":[],
                    "next_stage":"—",
                }
            auto_dir=amdir(ch.parent.parent,ch.name)
            if auto_dir.exists():
                shutil.rmtree(auto_dir)
            r=merge_chapter(
                ch,
                output_dir_override=auto_dir,
                progress_callback=lambda event: report(ch.name,event),
            )
            raw=json.loads((auto_dir/"merge-manifest.json").read_text(encoding="utf-8"))
            auto_manifest={"schema_version":1,"algorithm":"auto_merge_level1_complete","chapter":ch.name,"source_dir":str(ch),"output_dir":str(auto_dir),"total_height":int(raw.get("source_total_height") or 0),"artifacts":raw.get("outputs") or [],"pending_segments":[],"coverage":{"auto_segments":[[int(x["global_start"]),int(x["global_end"])] for x in (raw.get("outputs") or [])]},"v3_manifest":raw}
            (auto_dir/"auto-merge-manifest.json").write_text(json.dumps(auto_manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
            (auto_dir/"merge-manifest.json").unlink()
            promoted,promote_msg=_promote_level1_complete(ch)
            if not promoted: raise RuntimeError(promote_msg)
            clear_merge_failure(ch)
            report(ch.name,{"stage":"done","current":1,"total":1,"message":"capítulo concluído"})
            summary=_auto_merge_summary_payload(ch)
            return {
                "chapter":ch.name,
                "status":"ok",
                "merged_images":r.merged_images,
                "auto_merge_saved":r.merged_images,
                "auto_merge_folder":str(auto_dir),
                "auto_merge_files":summary["auto_merge_files"],
                "pending_files":[],
                "pending_segments_count":0,
                "residuals":[],
                "reason_codes":[],
                "next_stage":"—",
                "message":promote_msg,
            }
        except Exception as e:
            set_merge_failure(ch,e)
            report(ch.name,{"stage":"done","current":1,"total":1,"message":"capítulo finalizado"})
            failure=read_merge_failure(ch) or {}
            level1=failure.get("auto_merge_level1") or {}
            saved=int(level1.get("artifacts_count") or 0)
            summary=_auto_merge_summary_payload(ch,failure)
            return {
                "chapter":ch.name,
                "status":"partial" if saved else "error",
                "message":str(e),
                "auto_merge_saved":saved,
                "auto_merge_folder":level1.get("output_dir"),
                "auto_merge_files":summary["auto_merge_files"],
                "pending_files":summary["pending_files"],
                "pending_segments_count":summary["pending_segments_count"],
                "residuals":summary["residuals"],
                "reason_codes":summary["reason_codes"],
                "next_stage":"Auto-Merge Nível II" if summary["pending_segments_count"] else "Verificar ocorrência",
            }

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
            if not job.progress_detail:
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
        resolved=(part or {}).get("level2_resolved_segments") or []
        pending=(part or {}).get("pending_segments") or []
        pending_files=[]
        seen_pending=set()
        for seg in pending:
            for name in (seg.get("sources") or []):
                name=str(name)
                if name and name not in seen_pending:
                    seen_pending.add(name); pending_files.append(name)
        out.append({
            "chapter":ch.name,
            "status":"ok" if ok else "error",
            "message":msg,
            "resolved_segments":len(resolved),
            "pending_segments":len(pending),
            "stage_files":[str(x.get("file")) for x in resolved if isinstance(x,dict) and x.get("file")],
            "pending_files":pending_files,
            "residuals":[
                {"global_start":int(x["global_start"]),"global_end":int(x["global_end"])}
                for x in pending
                if x.get("global_start") is not None and x.get("global_end") is not None
            ],
            "reason_codes":[
                str(x.get("reason"))
                for x in pending
                if isinstance(x,dict) and x.get("reason")
            ],
            "stage_folder":str(l2dir(ch.parent.parent,ch.name)),
            "next_stage":"Auto-Merge Nível III" if pending else "—",
        })
        job.progress=i
    return out

def do_merge_level3(job,chs):
    out=[]
    for i,ch in enumerate(chs,1):
        job.message=f"Auto-Merge Nível III: capítulo {ch.name}..."
        try:
            failure=read_merge_failure(ch)
            part=(failure or {}).get("partition") or {}
            if not failure:
                out.append({"chapter":ch.name,"status":"error","message":"Falha/partição do Auto-Merge ausente."})
            elif not _is_level2_validated(failure):
                out.append({"chapter":ch.name,"status":"error","message":"Nível II ainda não foi validado."})
            elif not (part.get("pending_segments") or []):
                out.append({"chapter":ch.name,"status":"skip","message":"Nível II não possui residual pendente para o Nível III."})
            else:
                l3_ok,l3_msg,l3_manifest=process_merge_level3_pending(ch,part)
                if not l3_ok:
                    out.append({"chapter":ch.name,"status":"error","message":l3_msg or "Falha no Auto-Merge Nível III."})
                else:
                    residual=(l3_manifest or {}).get("residual_pending_segments") or []
                    safe=(l3_manifest or {}).get("safe_artifacts") or []
                    promoted=False
                    promote_msg=None
                    if not residual:
                        promoted,promote_msg=_promote_level3_complete(ch,part)
                        if promoted:
                            clear_merge_failure(ch)
                    status="ok" if (residual or promoted) else "error"
                    if residual:
                        if safe:
                            message=(
                                f"Auto-Merge Nível III analisado: {len(safe)} região(ões) SAFE "
                                f"e {len(residual)} região(ões) residual(is) ainda sem solução automática segura."
                            )
                        else:
                            message=(
                                f"Auto-Merge Nível III analisado: nenhum trecho pôde ser comprovado como SAFE; "
                                f"{len(residual)} região(ões) residual(is) permanecem pendentes."
                            )
                    elif promoted:
                        message="Auto-Merge Nível III analisado e resolvido automaticamente."
                    else:
                        message=l3_msg or "Auto-Merge Nível III analisado sem resultado promovível."
                    if promote_msg:
                        message=f"{message} {promote_msg}"
                    pending_files=[]
                    seen_pending=set()
                    for seg in residual:
                        for name in (seg.get("sources") or []):
                            name=str(name)
                            if name and name not in seen_pending:
                                seen_pending.add(name); pending_files.append(name)
                    out.append({
                        "chapter":ch.name,
                        "status":status,
                        "message":message,
                        "safe_segments":len(safe),
                        "residual_pending_segments":len(residual),
                        "promoted":bool(promoted),
                        "stage_files":[str(x.get("file")) for x in safe if isinstance(x,dict) and x.get("file")],
                        "pending_files":pending_files,
                        "residuals":[
                            {"global_start":int(x["global_start"]),"global_end":int(x["global_end"])}
                            for x in residual
                            if x.get("global_start") is not None and x.get("global_end") is not None
                        ],
                        "reason_codes":[
                            str(x.get("reason") or x.get("trigger_reason"))
                            for x in residual
                            if isinstance(x,dict) and (x.get("reason") or x.get("trigger_reason"))
                        ],
                        "stage_folder":str(l3dir(ch.parent.parent,ch.name)),
                        "next_stage":"Revisão Merge V2" if residual else "—",
                    })
        except Exception as exc:
            out.append({"chapter":ch.name,"status":"error","message":str(exc)})
        job.progress=i
    return out

def do_pdf(job,chs):
    from orquestracao.menu import run_pdf_batch
    generated=[]
    skipped=[]
    problems=[]
    total=len(chs)
    for i,ch in enumerate(chs,1):
        job.message=f"Gerar PDF: processando capítulo {ch.name} ({i}/{total})..."
        r=run_pdf_batch([ch],regenerate_existing=False)
        generated.extend(x.name for x in r["generated"])
        skipped.extend(x.name for x in r["skipped"])
        problems.extend({"chapter":c.name,"message":m} for c,m in r["problems"])
        job.progress=i
        job.message=f"Gerar PDF: {i}/{total} concluído(s)"
    return {"selected":total,"generated":generated,"skipped":skipped,"problems":problems}

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
        imgs=v3.merge_artifact_files(merge_output_dir(ch)); destdir=pmdir(manga,ch.name); destdir.mkdir(parents=True,exist_ok=True); dest=destdir/f"{ch.name}.pdf"
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
def do_clean_merged(job,manga,chs):
    from processamento.limpeza_baloes.bubble_cleaner import EasyOCRBackend,process_image,resolve_model
    from processamento.unificacao_imagens.image_stitcher import is_chapter_merged,merge_output_dir
    model=resolve_model(None); ocr=EasyOCRBackend(["en"]); out=[]
    total_chapters=max(1,len(chs))
    job.progress_value=0.0
    job.progress_max=float(total_chapters)
    for i,ch in enumerate(chs,1):
        chapter_base=float(i-1)
        job.progress_detail=f"Cap. {ch.name}: validando MERGE..."
        job.message=f"Texto Off — Merged: validando capítulo {ch.name} ({i}/{len(chs)})..."
        if not is_chapter_merged(ch):
            out.append({"chapter":ch.name,"status":"error","message":"MERGE oficial inválido ou ausente"})
            job.progress=i
            job.progress_value=float(i)
            job.progress_detail=f"Cap. {ch.name}: MERGE oficial inválido ou ausente"
            continue
        imgs=v3.merge_artifact_files(merge_output_dir(ch))
        if not imgs:
            out.append({"chapter":ch.name,"status":"error","message":"MERGE oficial sem imagens para limpeza"})
            job.progress=i
            job.progress_value=float(i)
            job.progress_detail=f"Cap. {ch.name}: MERGE oficial sem imagens para limpeza"
            continue
        target=tmdir(manga,ch.name)
        if target.is_dir(): shutil.rmtree(target)
        target.mkdir(parents=True,exist_ok=True)
        reports=[]; fails=[]
        total_images=max(1,len(imgs))
        for pi,img in enumerate(imgs,1):
            job.progress_value=chapter_base+(float(pi-1)/float(total_images))
            job.progress_detail=f"Cap. {ch.name}: imagem {pi}/{len(imgs)}"
            job.message=f"Texto Off — Merged · Capítulo {ch.name}: imagem {pi}/{len(imgs)}"
            try: reports.append(process_image(img,target,model,["en"],0.55,ocr_backend=ocr))
            except Exception as e: fails.append(f"{img.name}: {e}")
            job.progress_value=chapter_base+(float(pi)/float(total_images))
        manifest={
            "schema_version":1,
            "algorithm":"bubble_cleaner_v3_5",
            "source_stage":"MERGE",
            "source_immutable":True,
            "source_artifacts":[p.name for p in imgs],
            "pages_total":len(reports),
            "integrity_ok":bool(reports) and all(r["summary"]["integrity_ok"] for r in reports) and not fails,
            "failures":fails,
        }
        (target/"clean-manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
        out.append({"chapter":ch.name,"status":"ok" if not fails else "error","pages":len(reports),"failures":fails,"stage_folder":str(target)})
        job.progress=i
        job.progress_value=float(i)
        job.progress_detail=f"Cap. {ch.name}: concluído"
    return out

def reviewmod():
    from processamento.unificacao_imagens import image_stitcher_review
    return image_stitcher_review

def _level3_review_pending(ch,failure):
    # Retorna a fila autoritativa de Review. Com Level III válido,
    # somente residual_pending_segments pode seguir para revisão.
    import hashlib

    partition=failure.get("partition") or {}
    if not _is_level2_validated(failure):
        return None,None,"historical"

    level2_pending=partition.get("pending_segments") or []
    manga=ch.parent.parent
    manifest_path=l3dir(manga,ch.name)/"merge-level3-manifest.json"
    if not manifest_path.is_file():
        if level2_pending:
            return None,(
                "Auto-Merge Nível III ainda não foi validado para este capítulo."
            ),"level3_pending"
        return None,None,"level2"

    try:
        payload=json.loads(manifest_path.read_text(encoding="utf-8"))
        if payload.get("algorithm")!="merge_level3_structural_safe_v1":
            return None,"Manifesto Level III possui algoritmo não suportado.","level3"

        total=int(partition.get("total_height") or 0)
        if int(payload.get("total_height") or 0)!=total or total<=0:
            return None,"Manifesto Level III não corresponde ao total_height atual do Level II.","level3"

        level2_manifest_path=l2dir(manga,ch.name)/"merge-level2-manifest.json"
        if not level2_manifest_path.is_file():
            return None,"Manifesto Level II ausente para validar o Level III.","level3"
        expected_hash=hashlib.sha256(level2_manifest_path.read_bytes()).hexdigest()
        if str(payload.get("source_level2_sha256") or "")!=expected_hash:
            return None,(
                "Manifesto Level III está desatualizado em relação ao Level II; "
                "revalide o Level II para regenerar o Level III."
            ),"level3"

        parents=sorted(
            (int(x["global_start"]),int(x["global_end"]))
            for x in level2_pending
        )
        safe=payload.get("safe_artifacts") or []
        residual=payload.get("residual_pending_segments") or []
        children=sorted(
            [(int(x["global_start"]),int(x["global_end"])) for x in safe]
            + [(int(x["global_start"]),int(x["global_end"])) for x in residual]
        )

        if not parents:
            return None,"Level III existe, mas o Level II atual não possui pending_segments.","level3"

        ci=0
        for pstart,pend in parents:
            if pend<=pstart:
                return None,"Level II possui intervalo pending inválido.","level3"
            cursor=pstart
            while ci<len(children) and children[ci][0] < pend:
                cstart,cend=children[ci]
                if cstart!=cursor or cend<=cstart or cend>pend:
                    return None,(
                        "Level III não recompõe exatamente os pending_segments do Level II "
                        "(GAP/OVERLAP ou intervalo fora do pai)."
                    ),"level3"
                cursor=cend
                ci+=1
            if cursor!=pend:
                return None,(
                    "Level III não recompõe exatamente os pending_segments do Level II "
                    "(cobertura incompleta)."
                ),"level3"
        if ci!=len(children):
            return None,"Level III possui intervalo fora dos pending_segments do Level II.","level3"

        return (residual or None),None,"level3"
    except (OSError,ValueError,TypeError,KeyError,IndexError,json.JSONDecodeError) as exc:
        return None,f"Manifesto Level III inválido: {exc}","level3"


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
        level2_validated=_is_level2_validated(failure)
        pending_segments=None
        pending_source="historical"
        if level2_validated:
            pending_segments,pending_error,pending_source=_level3_review_pending(ch,failure)
            if pending_error:
                out.append({
                    "chapter":ch.name,
                    "status":"error",
                    "message":pending_error,
                    "path":None,
                    "max_source_images":limit,
                })
                job.progress=i
                continue
            if not pending_segments:
                out.append({
                    "chapter":ch.name,
                    "status":"error",
                    "message":(
                        "Level III não possui residual pendente para Review."
                        if pending_source=="level3"
                        else
                        "Level II validado sem segmentos pendentes; "
                        "Review não será gerado para o capítulo inteiro."
                    ),
                    "path":None,
                    "max_source_images":limit,
                })
                job.progress=i
                continue

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
                folder_name={
                    "pdf_merge":("03_PDF_MERGE",),
                    "auto_merge":("01_MERGE_PROCESSAMENTO","AUTO_MERGE"),
                    "merge_level2":("01_MERGE_PROCESSAMENTO","MERGE_LEVEL2"),
                    "merge_level3":("01_MERGE_PROCESSAMENTO","MERGE_LEVEL3"),
                    "text_off_merged":("04_TEXTO_OFF","MERGED"),
                    "merge":("02_MERGE",),
                }.get(kind)
                if not folder_name:
                    raise ValueError("Tipo de pasta inválido.")
                base=(manga/"FLUXO_SECUNDARIO").joinpath(*folder_name).resolve()
                target=base if (kind=="pdf_merge" and not chapter) else (base/chapter).resolve()
                if not target.is_relative_to(base) or not target.is_dir():
                    raise ValueError(f"Pasta {'/'.join(folder_name)} não encontrada.")
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
