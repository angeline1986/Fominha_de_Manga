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
def l3dir(m,c): return m/"FLUXO_SECUNDARIO"/"MERGE_LEVEL3"/c
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


def _promote_level2_complete(ch, part):
    """Promove Level II 100% PASSED para o MERGE oficial."""
    from datetime import datetime, timezone
    from PIL import Image
    from processamento.unificacao_imagens import image_stitcher as v3

    manga = ch.parent.parent
    level2_dir = l2dir(manga, ch.name)
    manifest_path = level2_dir / "merge-level2-manifest.json"

    if not manifest_path.is_file():
        return False, "Manifesto Level II não encontrado."

    try:
        level2_payload = json.loads(
            manifest_path.read_text(encoding="utf-8")
        )
    except Exception as exc:
        return False, f"Manifesto Level II inválido: {exc}"

    pending = level2_payload.get("pending_segments") or []
    if pending:
        return False, (
            "Level II ainda possui segmentos pendentes; "
            "promoção direta cancelada."
        )

    artifacts = level2_payload.get("artifacts") or []
    if not artifacts:
        return False, "Level II não possui artefatos PASSED."

    total_height = int(
        level2_payload.get("total_height")
        or part.get("total_height")
        or 0
    )
    if total_height <= 0:
        return False, "Altura total do Level II inválida."

    pieces = []

    try:
        for artifact in artifacts:
            start = int(artifact["global_start"])
            end = int(artifact["global_end"])
            filename = str(artifact["file"])

            if start < 0 or end <= start:
                return False, (
                    f"Intervalo Level II inválido: "
                    f"{start}..{end}."
                )

            source = level2_dir / filename
            if not source.is_file():
                return False, (
                    f"Artefato Level II ausente: {filename}."
                )

            pieces.append(
                {
                    "global_start": start,
                    "global_end": end,
                    "source": source,
                    "source_file": filename,
                }
            )
    except (KeyError, TypeError, ValueError) as exc:
        return False, (
            f"Metadados de artefato Level II inválidos: {exc}"
        )

    pieces.sort(
        key=lambda item: (
            item["global_start"],
            item["global_end"],
            item["source_file"],
        )
    )

    expected_start = 0
    expected_width = None

    for piece in pieces:
        start = piece["global_start"]
        end = piece["global_end"]
        source = piece["source"]

        if start != expected_start:
            relation = "lacuna" if start > expected_start else "sobreposição"
            return False, (
                f"Cobertura Level II inválida ({relation}): "
                f"esperado {expected_start}, encontrado {start}."
            )

        try:
            with Image.open(source) as im:
                width = int(im.width)
                height = int(im.height)
        except Exception as exc:
            return False, (
                f"Artefato Level II ilegível "
                f"{source.name}: {exc}"
            )

        expected_height = end - start
        if height != expected_height:
            return False, (
                f"Altura incompatível em {source.name}: "
                f"{height} != {expected_height}."
            )

        if expected_width is None:
            expected_width = width
        elif width != expected_width:
            return False, (
                f"Largura incompatível em {source.name}: "
                f"{width} != {expected_width}."
            )

        expected_start = end

    if expected_start != total_height:
        return False, (
            "Cobertura Level II incompleta: "
            f"{expected_start} != {total_height}."
        )

    official_dir = v3.merge_output_dir(ch)

    if official_dir.exists():
        if v3.is_chapter_merged(ch):
            return False, (
                "Já existe MERGE oficial válido para este capítulo."
            )

        return False, (
            "Já existe MERGE oficial não reconhecido; "
            "promoção cancelada por segurança."
        )

    official_dir.mkdir(
        parents=True,
        exist_ok=False,
    )

    outputs = []

    try:
        for index, piece in enumerate(pieces, 1):
            filename = f"merged-{index:03d}.png"
            destination = official_dir / filename

            # Preserva exatamente o artefato validado do Level II.
            shutil.copy2(
                piece["source"],
                destination,
            )

            outputs.append(
                {
                    "file": filename,
                    "global_start": piece["global_start"],
                    "global_end": piece["global_end"],
                    "width": expected_width,
                    "height": (
                        piece["global_end"]
                        - piece["global_start"]
                    ),
                    "sources": [],
                    "source_stage": "level2",
                    "source_file": piece["source_file"],
                }
            )

        manifest = {
            "schema_version": 1,
            "algorithm": "merge_level2_composition_v1",
            "status": "approved",
            "approved_at": datetime.now(
                timezone.utc
            ).isoformat(),
            "source_dir": str(ch),
            "output_dir": str(official_dir),
            "source_width": int(expected_width or 0),
            "source_total_height": total_height,
            "merged_images": len(outputs),
            "outputs": outputs,
            "validation": {
                "ok": True,
                "errors": [],
                "coverage_start": 0,
                "coverage_end": total_height,
            },
            "safety": {
                "source_files_modified": False,
                "forced_cut_without_white_band": False,
                "all_source_pixels_preserved_in_order": True,
                "level2_passed_artifacts_rerendered": False,
            },
            "composition": {
                "level2_manifest": (
                    "merge-level2-manifest.json"
                ),
                "review_manifest": None,
                "scope": "level2_all_passed",
            },
        }

        (
            official_dir / "merge-manifest.json"
        ).write_text(
            json.dumps(
                manifest,
                ensure_ascii=False,
                indent=2,
            ) + "\n",
            encoding="utf-8",
        )

        if not v3.is_chapter_merged(ch):
            raise RuntimeError(
                "MERGE Level II promovido, mas manifesto "
                "oficial não foi reconhecido."
            )

    except Exception as exc:
        if official_dir.is_dir():
            shutil.rmtree(official_dir)

        return False, (
            f"Falha ao promover Level II completo: {exc}"
        )

    return True, (
        f"Level II concluído e promovido para {official_dir}"
    )


def _promote_level3_complete(ch, part=None):
    """Promove Level II PASSED + Level III 100% SAFE para o MERGE oficial."""
    import hashlib
    from datetime import datetime, timezone
    from PIL import Image
    from processamento.unificacao_imagens import image_stitcher as v3

    manga = ch.parent.parent
    level2_dir = l2dir(manga, ch.name)
    level3_dir = l3dir(manga, ch.name)
    level2_manifest_path = level2_dir / "merge-level2-manifest.json"
    level3_manifest_path = level3_dir / "merge-level3-manifest.json"

    if not level2_manifest_path.is_file():
        return False, "Manifesto Level II não encontrado."
    if not level3_manifest_path.is_file():
        return False, "Manifesto Level III não encontrado."

    try:
        level2_payload = json.loads(level2_manifest_path.read_text(encoding="utf-8"))
        level3_payload = json.loads(level3_manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return False, f"Manifesto Level II/III inválido: {exc}"

    if level2_payload.get("algorithm") != "merge_level2_auto_segments":
        return False, "Manifesto Level II possui algoritmo não suportado."
    if level3_payload.get("algorithm") != "merge_level3_structural_safe_v1":
        return False, "Manifesto Level III possui algoritmo não suportado."

    total_height = int(
        level2_payload.get("total_height")
        or (part or {}).get("total_height")
        or 0
    )
    if total_height <= 0:
        return False, "Altura total inválida para composição Level II + III."
    if int(level3_payload.get("total_height") or 0) != total_height:
        return False, "Level III não corresponde ao total_height atual do Level II."

    expected_hash = hashlib.sha256(level2_manifest_path.read_bytes()).hexdigest()
    if str(level3_payload.get("source_level2_sha256") or "") != expected_hash:
        return False, (
            "Manifesto Level III está desatualizado em relação ao Level II; "
            "promoção direta cancelada."
        )

    level2_pending = level2_payload.get("pending_segments") or []
    level3_safe = level3_payload.get("safe_artifacts") or []
    level3_residual = level3_payload.get("residual_pending_segments") or []

    if not level2_pending:
        return False, "Level II não possui pending_segments para o Level III."
    if level3_residual:
        return False, (
            "Level III ainda possui residual pendente; "
            "promoção direta cancelada."
        )
    if not level3_safe:
        return False, "Level III não possui artefatos SAFE para promover."

    try:
        parents = sorted(
            (int(x["global_start"]), int(x["global_end"]))
            for x in level2_pending
        )
        children = sorted(
            (int(x["global_start"]), int(x["global_end"]))
            for x in level3_safe
        )
    except (KeyError, TypeError, ValueError) as exc:
        return False, f"Intervalos Level II/III inválidos: {exc}"

    ci = 0
    for pstart, pend in parents:
        if pstart < 0 or pend <= pstart:
            return False, "Level II possui pending_segment inválido."
        cursor = pstart
        while ci < len(children) and children[ci][0] < pend:
            cstart, cend = children[ci]
            if cstart != cursor or cend <= cstart or cend > pend:
                return False, (
                    "Level III SAFE não recompõe exatamente os pending_segments "
                    "do Level II (GAP/OVERLAP ou intervalo fora do pai)."
                )
            cursor = cend
            ci += 1
        if cursor != pend:
            return False, (
                "Level III SAFE não recompõe exatamente os pending_segments "
                "do Level II (cobertura incompleta)."
            )
    if ci != len(children):
        return False, (
            "Level III SAFE possui intervalo fora dos pending_segments do Level II."
        )

    pieces = []
    try:
        for artifact in level2_payload.get("artifacts") or []:
            pieces.append({
                "global_start": int(artifact["global_start"]),
                "global_end": int(artifact["global_end"]),
                "source": level2_dir / str(artifact["file"]),
                "source_file": str(artifact["file"]),
                "source_stage": "level2",
            })
        for artifact in level3_safe:
            pieces.append({
                "global_start": int(artifact["global_start"]),
                "global_end": int(artifact["global_end"]),
                "source": level3_dir / str(artifact["file"]),
                "source_file": str(artifact["file"]),
                "source_stage": "level3",
            })
    except (KeyError, TypeError, ValueError) as exc:
        return False, f"Metadados de composição Level II/III inválidos: {exc}"

    if not pieces:
        return False, "Composição Level II + III não possui artefatos."

    pieces.sort(
        key=lambda item: (
            item["global_start"],
            item["global_end"],
            item["source_stage"],
            item["source_file"],
        )
    )

    expected_start = 0
    expected_width = None
    for piece in pieces:
        start = piece["global_start"]
        end = piece["global_end"]
        source = piece["source"]
        if start != expected_start:
            relation = "lacuna" if start > expected_start else "sobreposição"
            return False, (
                f"Cobertura Level II + III inválida ({relation}): "
                f"esperado {expected_start}, encontrado {start}."
            )
        if end <= start:
            return False, f"Intervalo inválido em {piece['source_file']}: {start}..{end}."
        if not source.is_file():
            return False, f"Artefato ausente: {source}."
        try:
            with Image.open(source) as im:
                width = int(im.width)
                height = int(im.height)
        except Exception as exc:
            return False, f"Artefato ilegível {source.name}: {exc}"

        expected_height = end - start
        if height != expected_height:
            return False, (
                f"Altura incompatível em {source.name}: "
                f"{height} != {expected_height}."
            )
        if expected_width is None:
            expected_width = width
        elif width != expected_width:
            return False, (
                f"Largura incompatível em {source.name}: "
                f"{width} != {expected_width}."
            )
        expected_start = end

    if expected_start != total_height:
        return False, (
            "Cobertura Level II + III incompleta: "
            f"{expected_start} != {total_height}."
        )

    official_dir = v3.merge_output_dir(ch)
    if official_dir.exists():
        if v3.is_chapter_merged(ch):
            return False, "Já existe MERGE oficial válido para este capítulo."
        return False, (
            "Já existe MERGE oficial não reconhecido; "
            "promoção cancelada por segurança."
        )

    official_dir.mkdir(parents=True, exist_ok=False)
    outputs = []
    try:
        for index, piece in enumerate(pieces, 1):
            filename = f"merged-{index:03d}.png"
            destination = official_dir / filename
            shutil.copy2(piece["source"], destination)
            outputs.append({
                "file": filename,
                "global_start": piece["global_start"],
                "global_end": piece["global_end"],
                "width": expected_width,
                "height": piece["global_end"] - piece["global_start"],
                "sources": [],
                "source_stage": piece["source_stage"],
                "source_file": piece["source_file"],
            })

        manifest = {
            "schema_version": 1,
            "algorithm": "merge_level2_level3_composition_v1",
            "status": "approved",
            "approved_at": datetime.now(timezone.utc).isoformat(),
            "source_dir": str(ch),
            "output_dir": str(official_dir),
            "source_width": int(expected_width or 0),
            "source_total_height": total_height,
            "merged_images": len(outputs),
            "outputs": outputs,
            "validation": {
                "ok": True,
                "errors": [],
                "coverage_start": 0,
                "coverage_end": total_height,
            },
            "safety": {
                "source_files_modified": False,
                "forced_cut_without_white_band": False,
                "all_source_pixels_preserved_in_order": True,
                "level2_passed_artifacts_rerendered": False,
                "level3_safe_artifacts_rerendered": False,
            },
            "composition": {
                "level2_manifest": "merge-level2-manifest.json",
                "level3_manifest": "merge-level3-manifest.json",
                "review_manifest": None,
                "scope": "level3_all_safe",
            },
        }
        (official_dir / "merge-manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        if not v3.is_chapter_merged(ch):
            raise RuntimeError(
                "MERGE Level II + III promovido, mas manifesto oficial "
                "não foi reconhecido."
            )
    except Exception as exc:
        if official_dir.is_dir():
            shutil.rmtree(official_dir)
        return False, f"Falha ao promover Level III completo: {exc}"

    return True, (
        f"Level III resolveu todos os pendentes e a composição "
        f"Level II + III foi promovida para {official_dir}"
    )


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
    for old in dest.glob("safe-*.png"): old.unlink()

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
            name=f"safe-{out_index:03d}.png"; path=dest/name
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

    if not pending:
        total_height = int(
            part.get("total_height") or 0
        )

        intervals = sorted(
            (
                int(seg["global_start"]),
                int(seg["global_end"]),
            )
            for seg in (
                part.get("resolved_segments") or []
            )
        )

        complete_coverage = bool(
            total_height > 0
            and intervals
            and intervals[0][0] == 0
            and intervals[-1][1] == total_height
            and all(
                current_end == next_start
                for (
                    (_, current_end),
                    (next_start, _),
                )
                in zip(
                    intervals,
                    intervals[1:],
                )
            )
        )

        if complete_coverage:
            promoted, promote_msg = _promote_level2_complete(
                ch,
                part,
            )
            if not promoted:
                return False, promote_msg, part

            clear_merge_failure(ch)

            return True, (
                f"Nível II validou {len(resolved)} trecho(s) "
                "automático(s); nenhum trecho requer revisão. "
                f"{promote_msg}"
            ), part

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


def _is_level2_validated(failure):
    """Interpreta de forma única o estado persistido do Level II."""
    failure = failure or {}
    partition = failure.get("partition") or {}

    return bool(
        failure.get("level2_status") == "validated"
        or partition.get("level2_validated")
    )


def row_state(manga,ch):
    from processamento.unificacao_imagens.image_stitcher import is_chapter_merged, merge_output_dir
    md=merge_output_dir(ch); rd=rdir(manga,ch.name)
    merge_ok=False; merge_error=None
    try: merge_ok=bool(is_chapter_merged(ch))
    except Exception as exc: merge_error=str(exc)
    failure=read_merge_failure(ch); merge_failed=bool(failure)
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
    needs_review=bool(
        merge_failed
        and not validated_without_pending
        and (not has_level2 or level2_validated)
    )
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
        "merge_state":"concluido" if merge_ok else ("pendente_review" if needs_review else ("parcial" if (has_level2 or validated_without_pending) else ("pendente_review" if merge_failed else "novo"))),
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
        level3=None
        if ok and part and part.get("level2_validated") and (part.get("pending_segments") or []):
            l3_ok,l3_msg,l3_manifest=process_merge_level3_pending(ch,part)
            level3={"status":"ok" if l3_ok else "error","message":l3_msg,"safe_segments":len((l3_manifest or {}).get("safe_artifacts") or []),"residual_pending_segments":len((l3_manifest or {}).get("residual_pending_segments") or []),"promoted":False}
            if l3_ok and l3_manifest is not None and not (l3_manifest.get("residual_pending_segments") or []):
                promoted,promote_msg=_promote_level3_complete(ch,part)
                level3["promoted"]=bool(promoted)
                level3["status"]="ok" if promoted else "error"
                level3["message"]=f"{l3_msg} {promote_msg}"
                if promoted:
                    clear_merge_failure(ch)
        out.append({
            "chapter":ch.name,
            "status":"ok" if ok and (not level3 or level3["status"]=="ok") else "error",
            "message":msg if not level3 else f"{msg} {level3['message']}",
            "resolved_segments":len((part or {}).get("resolved_segments") or []),
            "pending_segments":len((part or {}).get("pending_segments") or []),
            "level3":level3,
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
        return (level2_pending or None),None,"level2"

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
