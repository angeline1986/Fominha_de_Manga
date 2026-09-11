#!/usr/bin/env python3
from __future__ import annotations
from collections import defaultdict
from typing import Callable, Any
import numpy as np
from processamento.unificacao_imagens.image_stitcher_level3 import (
    Level3Config, Level3Decision, Level3PendingRegion,
    analyze_structural_candidate, preprocess_for_structure,
)

DEFAULT_TARGET_HEIGHT = 7000
DEFAULT_MIN_CHUNK_HEIGHT = 3000
DEFAULT_MAX_CHUNK_HEIGHT = 12000
DEFAULT_COARSE_STEP = 256
DEFAULT_BIN_HEIGHT = 3000
DEFAULT_SEEDS_PER_BIN = 3
DEFAULT_REFINE_RADIUS = 128
DEFAULT_REFINE_STEP = 8

def _path_score(chunks, target_height):
    deviation=sum(abs(int(h)-int(target_height)) for h in chunks)
    imbalance=(max(chunks)-min(chunks)) if chunks else 0
    return (int(deviation),int(imbalance),len(chunks))

def _best_complete_path(*,start,end,safe_positions,min_chunk_height,max_chunk_height,target_height):
    nodes=[int(start)]+sorted({int(y) for y in safe_positions if int(start)<int(y)<int(end)})+[int(end)]
    best={int(start):((0,0,0),[int(start)],[])}
    for y in nodes[1:]:
        chosen=None
        for x in nodes:
            if x>=y: break
            prev=best.get(x)
            if prev is None: continue
            chunk=int(y)-int(x)
            if chunk<int(min_chunk_height) or chunk>int(max_chunk_height): continue
            _,bounds,chunks=prev
            cc=chunks+[chunk]; cb=bounds+[int(y)]
            cand=(_path_score(cc,int(target_height)),cb,cc)
            if chosen is None or (cand[0],tuple(cand[1]))<(chosen[0],tuple(chosen[1])): chosen=cand
        if chosen is not None: best[int(y)]=chosen
    result=best.get(int(end))
    return list(result[1]) if result is not None else None

def _cheap_metrics(gray, *, global_y, image_global_start, config):
    local_y=int(global_y)-int(image_global_start)
    half=max(20,int(config.analysis_half_window))
    top=max(0,local_y-half); bottom=min(gray.shape[0],local_y+half+1)
    window=gray[top:bottom,:]
    if window.shape[0]<5: return float("inf"),float("inf")
    blurred,edges=preprocess_for_structure(window,config=config)
    cut_y=local_y-top
    bh=max(1,int(config.cut_band_half_height))
    bt=max(0,cut_y-bh); bb=min(blurred.shape[0],cut_y+bh+1)
    band=blurred[bt:bb,:]; eb=edges[bt:bb,:]
    if band.size==0 or eb.size==0: return float("inf"),float("inf")
    return float(np.std(band)), float(np.count_nonzero(eb))/float(eb.size)

def _rank(std,edge,cfg):
    sr=max(1e-9,float(cfg.uniform_std_max)); er=max(1e-9,float(cfg.safe_edge_density_max))
    return (std/sr+edge/er, edge, std)

def _shortlist(gray, *, start, lower, upper, cfg, coarse_step, bin_height, seeds_per_bin, refine_radius, refine_step):
    coarse=list(range(lower,upper+1,max(1,coarse_step)))
    if coarse and coarse[-1]!=upper: coarse.append(upper)
    bins=defaultdict(list)
    for y in coarse:
        std,edge=_cheap_metrics(gray,global_y=y,image_global_start=start,config=cfg)
        bins[(y-lower)//max(1,bin_height)].append((_rank(std,edge,cfg),y,std,edge))
    seeds=[]; seed_metrics=[]
    for b in sorted(bins):
        for score,y,std,edge in sorted(bins[b],key=lambda t:(t[0],t[1]))[:max(1,seeds_per_bin)]:
            seeds.append(y); seed_metrics.append({"bin":b,"y":y,"band_std":round(std,6),"edge_density":round(edge,8),"rank_score":round(score[0],6)})
    candidates=set()
    for seed in seeds:
        lo=max(lower,seed-max(0,refine_radius)); hi=min(upper,seed+max(0,refine_radius))
        for y in range(lo,hi+1,max(1,refine_step)): candidates.add(y)
        candidates.add(seed)
    return sorted(candidates), {"coarse_positions":len(coarse),"bins":len(bins),"seed_count":len(seeds),"shortlisted_candidates":len(candidates),"seed_metrics":seed_metrics}

def estimate_directed_validation_count(global_start,global_end,*,min_chunk_height=DEFAULT_MIN_CHUNK_HEIGHT,bin_height=DEFAULT_BIN_HEIGHT,seeds_per_bin=DEFAULT_SEEDS_PER_BIN,refine_radius=DEFAULT_REFINE_RADIUS,refine_step=DEFAULT_REFINE_STEP):
    start=int(global_start); end=int(global_end); mh=max(1,int(min_chunk_height))
    lower=start+mh; upper=end-mh
    if lower>upper:return 0
    span=upper-lower+1; bins=max(1,(span+bin_height-1)//bin_height)
    per_seed=(2*refine_radius)//max(1,refine_step)+2
    return int(bins*max(1,seeds_per_bin)*per_seed)

def find_global_safe_composition(image,*,global_start,global_end,config=None,target_height=DEFAULT_TARGET_HEIGHT,min_chunk_height=DEFAULT_MIN_CHUNK_HEIGHT,max_chunk_height=DEFAULT_MAX_CHUNK_HEIGHT,coarse_step=DEFAULT_COARSE_STEP,bin_height=DEFAULT_BIN_HEIGHT,seeds_per_bin=DEFAULT_SEEDS_PER_BIN,refine_radius=DEFAULT_REFINE_RADIUS,refine_step=DEFAULT_REFINE_STEP,progress_callback:Callable[[int,int],None]|None=None)->dict[str,Any]:
    start=int(global_start); end=int(global_end)
    if end<=start: raise ValueError("Intervalo inválido para Auto-Merge Nível IV.")
    min_h=max(1,int(min_chunk_height)); max_h=max(min_h,int(max_chunk_height)); target=max(min_h,min(max_h,int(target_height)))
    height=end-start; region=Level3PendingRegion(start,end); cfg=config or Level3Config()
    base={"evaluated_candidates":0,"eligible_candidates":0,"safe_candidates":0,"decision_counts":{},"reason_counts":{},"selected_diagnostics":[],"search_passes":1,"strategy":"directed_coarse_refine_v1"}
    if height<=max_h:
        return {**base,"resolved":True,"boundaries":[start,end],"cuts":[],"chunks":[height],"preselection":{"coarse_positions":0,"bins":0,"seed_count":0,"shortlisted_candidates":0,"seed_metrics":[]}}
    lower=start+min_h; upper=end-min_h; eligible=max(0,upper-lower+1)
    if lower>upper:
        return {**base,"resolved":False,"boundaries":None,"cuts":[],"chunks":[],"eligible_candidates":eligible,"preselection":{"coarse_positions":0,"bins":0,"seed_count":0,"shortlisted_candidates":0,"seed_metrics":[]}}
    gray=np.asarray(image,dtype=np.uint8)
    candidates,pre=_shortlist(gray,start=start,lower=lower,upper=upper,cfg=cfg,coarse_step=max(1,int(coarse_step)),bin_height=max(1,int(bin_height)),seeds_per_bin=max(1,int(seeds_per_bin)),refine_radius=max(0,int(refine_radius)),refine_step=max(1,int(refine_step)))
    safe={}; dc={}; rc={}
    for i,y in enumerate(candidates,1):
        r=analyze_structural_candidate(gray,candidate_y=int(y),region=region,image_global_start=start,config=cfg)
        dc[r.decision.value]=dc.get(r.decision.value,0)+1; rc[r.reason]=rc.get(r.reason,0)+1
        if r.decision==Level3Decision.SAFE: safe[int(y)]=r
        if progress_callback: progress_callback(i,max(1,len(candidates)))
    bounds=_best_complete_path(start=start,end=end,safe_positions=list(safe),min_chunk_height=min_h,max_chunk_height=max_h,target_height=target)
    common={"evaluated_candidates":len(candidates),"eligible_candidates":eligible,"safe_candidates":len(safe),"decision_counts":dc,"reason_counts":rc,"search_passes":1,"strategy":"directed_coarse_refine_v1","preselection":pre}
    if bounds is None:
        return {**common,"resolved":False,"boundaries":None,"cuts":[],"chunks":[],"selected_diagnostics":[]}
    cuts=bounds[1:-1]
    return {**common,"resolved":True,"boundaries":bounds,"cuts":cuts,"chunks":[b-a for a,b in zip(bounds,bounds[1:])],"selected_diagnostics":[{**safe[int(y)].as_dict(),"selected_y":int(y)} for y in cuts]}
