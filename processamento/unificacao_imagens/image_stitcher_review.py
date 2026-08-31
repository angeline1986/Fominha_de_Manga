#!/usr/bin/env python3
"""Exception-review flow for the frozen Merge V3."""
from __future__ import annotations
import json, re, shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from PIL import Image
from processamento.unificacao_imagens import image_stitcher as v3

SECONDARY = "FLUXO_SECUNDARIO"
REVIEW = "MERGE_REVIEW"
EXTRA_LIMIT = 1000
REVIEW_MAX = v3.DEFAULT_MAX_CHUNK_HEIGHT + EXTRA_LIMIT

def _key(p: Path):
    return [int(x) if x.isdigit() else x.lower() for x in re.split(r"(\d+)", p.name)]

def _official(manga: Path, chapter: str) -> Path:
    return manga / SECONDARY / "MERGE" / chapter

def _review(manga: Path, chapter: str) -> Path:
    return manga / SECONDARY / REVIEW / chapter

def _official_valid(manga: Path, chapter: str) -> bool:
    d = _official(manga, chapter)
    m = d / "merge-manifest.json"
    if not m.is_file() or not list(d.glob("merged-*.png")):
        return False
    try:
        json.loads(m.read_text(encoding="utf-8"))
        return True
    except Exception:
        return False

def _pending(manga: Path):
    img = manga / "IMG"
    if not img.is_dir():
        return []
    return sorted(
        [p for p in img.iterdir() if p.is_dir() and v3.list_pages(p) and not _official_valid(manga, p.name)],
        key=_key,
    )

def _strict_candidates(infos, bands, current, upper):
    found = []
    for b in bands:
        center = (b.start + b.end) // 2
        if not (current + v3.DEFAULT_MIN_CHUNK_HEIGHT <= center <= upper):
            continue
        if b.height < v3.DEFAULT_MIN_WHITE_BAND:
            continue
        page, local = v3.page_at_y(infos, center)
        found.append({
            "center": center, "distance": center-current, "height": b.height,
            "ratio": b.white_ratio_mean, "page": page, "local_y": local,
        })
    return sorted(found, key=lambda x: x["center"])

def _v3_from(origin, total_height, bands):
    shifted = []
    for b in bands:
        if b.end <= origin:
            continue
        class B: pass
        x = B()
        x.start, x.end = b.start-origin, b.end-origin
        x.height, x.white_ratio_mean = b.height, b.white_ratio_mean
        shifted.append(x)
    cuts, _ = v3.choose_cuts(
        total_height-origin, shifted,
        target_height=v3.DEFAULT_TARGET_HEIGHT,
        search_before=v3.DEFAULT_SEARCH_BEFORE,
        search_after=v3.DEFAULT_SEARCH_AFTER,
        min_chunk_height=v3.DEFAULT_MIN_CHUNK_HEIGHT,
        min_white_band=v3.DEFAULT_MIN_WHITE_BAND,
        max_chunk_height=v3.DEFAULT_MAX_CHUNK_HEIGHT,
    )
    result = []
    for cut in cuts:
        item = dict(cut)
        item["center"] += origin
        if "band_start" in item: item["band_start"] += origin
        if "band_end" in item: item["band_end"] += origin
        result.append(item)
    return result

def build_proposal(total_height, infos, bands):
    cuts = _v3_from(0, total_height, bands)
    proposal = []
    current = cuts[-1]["center"] if cuts else 0

    while total_height-current > v3.DEFAULT_MAX_CHUNK_HEIGHT:
        hard = min(total_height-v3.DEFAULT_MIN_CHUNK_HEIGHT, current+v3.DEFAULT_MAX_CHUNK_HEIGHT)
        safe = _strict_candidates(infos, bands, current, hard)
        if safe:
            chosen, strategy = safe[-1], "strict_safe_zone"
        else:
            extended = min(total_height-v3.DEFAULT_MIN_CHUNK_HEIGHT, current+REVIEW_MAX)
            safe = [x for x in _strict_candidates(infos, bands, current, extended) if x["center"] > hard]
            if safe:
                chosen, strategy = safe[0], "strict_small_extension"
            else:
                # Terceira estratégia exclusiva do fluxo de REVIEW:
                # procura a primeira faixa que continue atendendo aos mesmos
                # critérios estritos de branco do V3, mesmo além de 13.000 px.
                # Não há corte forçado; a saída continua dependendo de revisão visual.
                review_upper = total_height - v3.DEFAULT_MIN_CHUNK_HEIGHT
                farther = [
                    x for x in _strict_candidates(infos, bands, current, review_upper)
                    if x["center"] > extended
                ]
                if not farther:
                    return None, proposal, (
                        "Nenhuma faixa branca segura foi encontrada após o último corte. "
                        "Nenhuma proposta foi criada."
                    )
                chosen, strategy = farther[0], "strict_extended_safe_zone"

        cut = {
            "center": chosen["center"],
            "band_height": chosen["height"],
            "white_ratio_mean": chosen["ratio"],
            "page": chosen["page"],
            "local_y": chosen["local_y"],
            "review_strategy": strategy,
        }
        cuts.append(cut)
        proposal.append({**chosen, "strategy": strategy})
        current = chosen["center"]

        continuation = _v3_from(current, total_height, bands)
        cuts.extend(continuation)
        if continuation:
            current = continuation[-1]["center"]

    cuts = sorted({int(c["center"]): c for c in cuts}.values(), key=lambda x: x["center"])
    bounds = [0] + [int(c["center"]) for c in cuts] + [total_height]
    proposal_by_center = {int(x["center"]): x for x in proposal}
    oversized = []
    for a,b in zip(bounds,bounds[1:]):
        size = b-a
        if size <= REVIEW_MAX:
            continue
        rescue = proposal_by_center.get(int(b))
        if not rescue or rescue.get("strategy") != "strict_extended_safe_zone":
            oversized.append((a,b,size))

    if oversized:
        a,b,size = oversized[0]
        return None, proposal, f"Proposta ainda contém trecho não justificado de {size:,} px ({a:,}–{b:,})."
    return cuts, proposal, None



def _sample_tail_quality(page, *, tail_height=220, sample_width=256):
    import numpy as np
    with Image.open(page) as im:
        rgb = im.convert("RGB")
        w, h = rgb.size
        if h < 40:
            return None
        th = min(tail_height, max(40, h // 4))
        sw = min(sample_width, w)
        x0 = max(0, (w - sw) // 2)
        arr = np.asarray(rgb.crop((x0, 0, x0 + sw, h)), dtype=np.float32)
        tail = arr[h-th:h]
        prev = arr[max(0, h-2*th):h-th]
        flat = tail.reshape(-1, 3)
        std = float(flat.std(axis=0).max())
        dx = float(np.abs(np.diff(tail, axis=1)).mean()) if tail.shape[1] > 1 else 0.0
        dy = float(np.abs(np.diff(tail, axis=0)).mean()) if tail.shape[0] > 1 else 0.0
        edge = max(dx, dy)
        if prev.size:
            n = min(len(tail), len(prev))
            transition = float(np.abs(tail[:n] - prev[-n:]).mean())
        else:
            transition = 0.0
        score = std + edge * 1.8 + transition * 0.6
        return {
            "score": round(score, 4),
            "std": round(std, 4),
            "edge": round(edge, 4),
            "transition": round(transition, 4),
            "tail_height": int(th),
        }


def _natural_page_end_candidates(pages, infos, start, end, allowed_end, max_source_images):
    source_indexes = [
        i for i, info in enumerate(infos)
        if min(end, info.global_end) > max(start, info.global_start)
    ]
    if not source_indexes:
        return []
    first_idx = source_indexes[0]
    max_idx = min(len(infos) - 1, first_idx + int(max_source_images) - 1)
    candidates = []
    for idx in range(max_idx, first_idx - 1, -1):
        info = infos[idx]
        center = int(info.global_end)
        if center <= start + v3.DEFAULT_MIN_CHUNK_HEIGHT:
            continue
        if center > allowed_end:
            continue
        if end - center < v3.DEFAULT_MIN_CHUNK_HEIGHT:
            continue
        quality = _sample_tail_quality(pages[idx])
        if not quality:
            continue
        if quality["std"] > 28.0 or quality["edge"] > 18.0 or quality["score"] > 62.0:
            continue
        page, local = v3.page_at_y(infos, max(start, center - 1))
        candidates.append({
            "center": center,
            "page": page,
            "local_y": local + 1,
            "review_strategy": "natural_source_page_end",
            "source_page_index": idx,
            "source_page_file": pages[idx].name,
            "tail_quality": quality,
            "uses_source_count": idx - first_idx + 1,
        })
    return candidates

def _uniform_band_candidates(pages, infos, sample_width=256, band_height=18, max_channel_std=7.0, max_edge_mean=10.0):
    import numpy as np
    out=[]; gy=0
    for page,info in zip(pages,infos):
        with Image.open(page) as im:
            rgb=im.convert("RGB"); w,h=rgb.size
            if h < band_height: gy += h; continue
            sw=min(sample_width,w); x0=max(0,(w-sw)//2)
            arr=np.asarray(rgb.crop((x0,0,x0+sw,h)),dtype=np.float32)
            step=max(4,band_height//2)
            for y in range(0,h-band_height+1,step):
                strip=arr[y:y+band_height]; flat=strip.reshape(-1,3)
                std=float(flat.std(axis=0).max())
                dx=float(np.abs(np.diff(strip,axis=1)).mean()) if strip.shape[1]>1 else 0.0
                dy=float(np.abs(np.diff(strip,axis=0)).mean()) if strip.shape[0]>1 else 0.0
                edge=max(dx,dy)
                if std<=max_channel_std and edge<=max_edge_mean:
                    out.append({"center":int(gy+y+band_height//2),"band_height":band_height,"uniform_std":std,"edge_mean":edge,"review_strategy":"uniform_color_safe_band"})
        gy += info.height
    return out

def _choose_uniform_cut(cands, infos, start, end, allowed_end):
    lower=start+v3.DEFAULT_MIN_CHUNK_HEIGHT; upper=min(allowed_end,end-v3.DEFAULT_MIN_CHUNK_HEIGHT)
    target=start+v3.DEFAULT_TARGET_HEIGHT; possible=[]
    for c in cands:
        center=int(c["center"])
        if lower<=center<=upper:
            page,local=v3.page_at_y(infos,center); x=dict(c); x["page"]=page; x["local_y"]=local; possible.append(x)
    if not possible: return None
    return sorted(possible,key=lambda x:(abs(x["center"]-target),x["uniform_std"],x["edge_mean"],x["center"]))[0]
def _segment_sources(infos, start, end):
    return [info for info in infos if min(end, info.global_end) > max(start, info.global_start)]



def _enforce_source_limit(cuts, infos, bands, total_height, max_source_images, pages=None):
    limit = int(max_source_images)
    if limit < 2:
        return None, [], "O limite mínimo é 2 imagens de origem por merge."

    centers = {int(c["center"]): dict(c) for c in cuts}
    inserted = []
    uniform = None

    for _ in range(10000):
        bounds = [0] + sorted(centers) + [total_height]
        violation = None
        for start, end in zip(bounds, bounds[1:]):
            sources = _segment_sources(infos, start, end)
            if len(sources) > limit:
                violation = (start, end, sources)
                break

        if violation is None:
            return [centers[k] for k in sorted(centers)], inserted, None

        start, end, sources = violation
        allowed_end = sources[limit - 1].global_end
        target = start + v3.DEFAULT_TARGET_HEIGHT
        chosen = None

        if pages is not None:
            natural = _natural_page_end_candidates(
                pages, infos, start, end, allowed_end, limit
            )
            if natural:
                best_count = max(x["uses_source_count"] for x in natural)
                same_count = [x for x in natural if x["uses_source_count"] == best_count]
                chosen = sorted(
                    same_count,
                    key=lambda x: (
                        x["tail_quality"]["score"],
                        abs(x["center"] - target),
                        x["center"],
                    )
                )[0]

        if chosen is None:
            lower = start + v3.DEFAULT_MIN_CHUNK_HEIGHT
            upper = min(allowed_end, end - v3.DEFAULT_MIN_CHUNK_HEIGHT)
            white = []
            for b in bands:
                center = (b.start + b.end) // 2
                if center in centers or not (lower <= center <= upper):
                    continue
                if b.height < v3.DEFAULT_MIN_WHITE_BAND:
                    continue
                page, local = v3.page_at_y(infos, center)
                white.append({
                    "center": center,
                    "band_height": b.height,
                    "white_ratio_mean": b.white_ratio_mean,
                    "page": page,
                    "local_y": local,
                    "review_strategy": "source_limit_safe_white_band",
                })
            if white:
                chosen = sorted(
                    white,
                    key=lambda x: (
                        abs(x["center"] - target),
                        -x["band_height"],
                        -x["white_ratio_mean"],
                        x["center"],
                    )
                )[0]

        if chosen is None:
            if pages is None:
                return None, inserted, "Detector de faixa uniforme sem páginas de origem."
            if uniform is None:
                uniform = _uniform_band_candidates(pages, infos)
            chosen = _choose_uniform_cut(uniform, infos, start, end, allowed_end)
            if chosen is None:
                return None, inserted, (
                    f"Não existe fim natural, faixa branca nem faixa uniforme segura "
                    f"que mantenha este trecho em até {limit} imagens de origem. "
                    "Aumente o máximo e regenere a proposta."
                )

        centers[int(chosen["center"])] = chosen
        inserted.append(dict(chosen))

    return None, inserted, "Limite interno atingido ao planejar os cortes."


def _render(pages, cuts, dest):
    dest.mkdir(parents=True, exist_ok=True)
    for p in dest.glob("merged-*.png"): p.unlink()
    spans=[]; y=0; width=None
    for p in pages:
        with Image.open(p) as im:
            if width is None: width=im.width
            if im.width != width: raise ValueError(f"Largura divergente: {p.name}")
            spans.append((p,y,y+im.height)); y += im.height
    bounds=[0]+[int(c["center"]) for c in cuts]+[y]
    outputs=[]
    for i,(start,end) in enumerate(zip(bounds,bounds[1:]),1):
        canvas=Image.new("RGB",(width,end-start),"white")
        for p,p0,p1 in spans:
            lo,hi=max(start,p0),min(end,p1)
            if hi<=lo: continue
            with Image.open(p) as im:
                crop=im.convert("RGB").crop((0,lo-p0,width,hi-p0))
                canvas.paste(crop,(0,lo-start))
        target=dest/f"merged-{i:03d}.png"
        canvas.save(target,"PNG"); outputs.append(target)
    return outputs,bounds

def generate_candidate(manga, chapter, *, max_source_images=8):
    pages=v3.list_pages(chapter)
    infos,bands,total,_=v3.analyze_chapter(
        pages, sample_width=v3.DEFAULT_SAMPLE_WIDTH,
        light_threshold=v3.DEFAULT_LIGHT_THRESHOLD,
        white_ratio_threshold=v3.DEFAULT_WHITE_RATIO,
    )
    cuts,proposal,error=build_proposal(total,infos,bands)
    if error: return False,error,None
    cuts,limit_cuts,limit_error=_enforce_source_limit(cuts,infos,bands,total,max_source_images,pages=pages)
    if limit_error: return False,limit_error,None
    proposal=list(proposal)+list(limit_cuts)
    dest=_review(manga,chapter.name)
    outputs,bounds=_render(pages,cuts,dest)
    manifest={
        "schema_version":1,"status":"candidate","algorithm":"merge_review_v1",
        "created_at":datetime.now(timezone.utc).isoformat(),"chapter":chapter.name,
        "source_pages":[p.name for p in pages],"proposal":proposal,"cuts":cuts,
        "boundaries":bounds,"outputs":[p.name for p in outputs],
        "policy":{"main_v3_modified":False,"forced_cut":False,
                  "min_white_band":v3.DEFAULT_MIN_WHITE_BAND,
                  "normal_max_chunk_height":v3.DEFAULT_MAX_CHUNK_HEIGHT,
                  "review_max_chunk_height":REVIEW_MAX,"small_extension_limit":EXTRA_LIMIT,
                  "extended_safe_zone":True,
                  "extended_safe_zone_rule":"first_strict_white_band_after_review_max",
                  "max_source_images":int(max_source_images),
                  "source_limit_rule":"natural_page_end_then_white_then_uniform_within_user_limit",
                  "uniform_color_fallback":"MERGE_REVIEW_ONLY"},
    }
    (dest/"merge-review.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    max_used=max((len(_segment_sources(infos,a,b)) for a,b in zip(bounds,bounds[1:])),default=0)
    return True,f"Proposta: {len(pages)} originais → {len(outputs)} merges; máximo utilizado: {max_used}/{int(max_source_images)} originais por merge.",dest

def approve(manga, chapter):
    src=_review(manga,chapter); mf=src/"merge-review.json"
    if not mf.is_file(): return False,"Nenhuma proposta encontrada."

    chapter_dir=manga/"IMG"/chapter
    dst=_official(manga,chapter)

    if dst.exists():
        if v3.is_chapter_merged(chapter_dir):
            return False,"Já existe MERGE oficial válido para este capítulo."
        stale_manifest=dst/"merge-manifest.json"
        stale_review_promotion=False
        if stale_manifest.is_file():
            try:
                stale_payload=json.loads(stale_manifest.read_text(encoding="utf-8"))
                stale_review_promotion=stale_payload.get("algorithm")=="merge_review_v1_approved"
            except (OSError,ValueError,TypeError,json.JSONDecodeError):
                stale_review_promotion=False
        if stale_review_promotion:
            shutil.rmtree(dst)
        else:
            return False,"Já existe MERGE oficial não reconhecido; promoção cancelada por segurança."

    payload=json.loads(mf.read_text(encoding="utf-8"))
    outputs=sorted(src.glob("merged-*.png"),key=_key)
    if not outputs: return False,"Proposta sem imagens."

    boundaries=payload.get("boundaries") or []
    if len(boundaries) != len(outputs)+1:
        return False,"Manifesto da proposta possui boundaries incompatíveis com as imagens."

    official_outputs=[]
    width=None
    for index,p in enumerate(outputs):
        with Image.open(p) as im:
            im.load()
            if width is None: width=im.width
            elif im.width != width: return False,f"Largura divergente na proposta: {p.name}"
            start=int(boundaries[index]); end=int(boundaries[index+1])
            if end-start != im.height: return False,f"Altura divergente na proposta: {p.name}"
            official_outputs.append({"file":p.name,"width":im.width,"height":im.height,"global_start":start,"global_end":end,"sources":[]})

    official_manifest={
        "schema_version":1,
        "algorithm":"merge_review_v1_approved",
        "status":"approved",
        "approved_at":datetime.now(timezone.utc).isoformat(),
        "source_dir":str(chapter_dir),
        "output_dir":str(dst),
        "source_pages":len(payload.get("source_pages") or []),
        "source_width":int(width or 0),
        "source_total_height":int(boundaries[-1]),
        "merged_images":len(official_outputs),
        "parameters":{"target_height":v3.DEFAULT_TARGET_HEIGHT,"search_before":v3.DEFAULT_SEARCH_BEFORE,"search_after":v3.DEFAULT_SEARCH_AFTER,"min_chunk_height":v3.DEFAULT_MIN_CHUNK_HEIGHT,"min_white_band":v3.DEFAULT_MIN_WHITE_BAND,"max_chunk_height":REVIEW_MAX,"white_ratio":v3.DEFAULT_WHITE_RATIO,"light_threshold":v3.DEFAULT_LIGHT_THRESHOLD,"sample_width":v3.DEFAULT_SAMPLE_WIDTH},
        "cuts":payload.get("cuts") or [],
        "decisions":payload.get("proposal") or [],
        "outputs":official_outputs,
        "validation":{"ok":True,"errors":[],"coverage_start":0,"coverage_end":int(boundaries[-1])},
        "safety":{"source_files_modified":False,"forced_cut_without_white_band":False,"all_source_pixels_preserved_in_order":True,"main_v3_modified":False},
        "review":{"created_at":payload.get("created_at"),"policy":payload.get("policy") or {},"original_manifest":"merge-review.json"},
    }

    try:
        dst.mkdir(parents=True)
        for p in outputs: shutil.copy2(p,dst/p.name)
        (dst/"merge-manifest.json").write_text(json.dumps(official_manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        if not v3.is_chapter_merged(chapter_dir): raise RuntimeError("MERGE promovido, mas manifesto oficial não foi reconhecido.")
    except Exception as exc:
        if dst.is_dir(): shutil.rmtree(dst)
        return False,f"Falha ao promover MERGE: {exc}"

    return True,f"Merge promovido e validado em {dst}"

def _parse_review_selection(raw: str, total: int) -> list[int]:
    value = raw.strip().lower()
    if value in {"todos", "todas", "all"}:
        return list(range(1, total + 1))
    selected = set()
    for chunk in value.split(","):
        part = chunk.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            a, b = int(a), int(b)
            if a > b:
                a, b = b, a
            selected.update(range(a, b + 1))
        else:
            selected.add(int(part))
    return sorted(i for i in selected if 1 <= i <= total)


def _choose_review_chapters(manga, ask_number, print_header, print_option, c):
    img = manga / "IMG"
    chapters = sorted(
        [p for p in img.iterdir() if p.is_dir() and v3.list_pages(p)],
        key=_key,
    ) if img.is_dir() else []
    if not chapters:
        print(c("warning", "Nenhum capítulo com imagens encontrado."))
        return []

    print_header(manga.name.upper())
    print_option(1, "Todos os capítulos")
    print_option(2, "Ainda não unificados")
    print_option(3, "Selecionar capítulos")
    print_option(0, "Voltar")
    mode = ask_number("\nSelecione uma opção › ", {0, 1, 2, 3})
    if mode == 0:
        return []
    if mode == 1:
        return chapters
    if mode == 2:
        result = [p for p in chapters if not _official_valid(manga, p.name)]
        if not result:
            print(c("success", "Todos os capítulos possuem MERGE oficial."))
        return result

    print_header("SELECIONAR CAPÍTULOS")
    for i, chapter in enumerate(chapters, 1):
        official = _official_valid(manga, chapter.name)
        status = "MERGE" if official else "PENDENTE"
        print(
            f"  {c('number', str(i)+'.', bold=True)} "
            f"{chapter.name:<32} "
            f"{c('success' if official else 'warning', status)}"
        )
    raw = input(c("prompt", "\nCapítulos (1,2,5 ou 1,3,5-9,12 ou todos) › ", bold=True))
    try:
        indexes = _parse_review_selection(raw, len(chapters))
    except ValueError:
        print(c("error", "Seleção inválida."))
        return []
    return [chapters[i - 1] for i in indexes]


def _run_chapter_review(manga, chapter, ask_number, print_header, print_option, c):
    while True:
        has = (_review(manga, chapter.name) / "merge-review.json").is_file()
        official = _official_valid(manga, chapter.name)
        print_header(f"CAPÍTULO {chapter.name}")
        print(c("success" if official else "warning",
                "Status: MERGE oficial existente" if official else "Status: ainda não unificado"))
        print_option(1, "Gerar merge proposto", "Saída isolada em MERGE_REVIEW")
        if has and not official:
            print_option(2, "Aprovar merge", "Após sua validação visual")
        if has:
            print_option(3, "Rejeitar proposta", "Remove apenas MERGE_REVIEW")
        print_option(0, "Voltar")

        valid = {0, 1}
        if has:
            valid.add(3)
            if not official:
                valid.add(2)
        action = ask_number("\nSelecione uma opção › ", valid)
        if action == 0:
            return
        if action == 1:
            ok, msg, dest = generate_candidate(manga, chapter)
            print(c("success" if ok else "warning", msg))
            if dest:
                print(c("muted", f"└─ {dest}"))
        elif action == 2:
            if ask_number("\nVocê validou visualmente a proposta? 1=Sim 2=Não › ", {1, 2}) != 1:
                continue
            ok, msg = approve(manga, chapter.name)
            print(c("success" if ok else "error", msg))
            if ok:
                return
        elif action == 3:
            if ask_number("\nApagar somente a proposta? 1=Sim 2=Não › ", {1, 2}) == 1:
                shutil.rmtree(_review(manga, chapter.name))
                print(c("success", "Proposta removida. IMG e MERGE oficial não foram alterados."))


def run_merge_review_flow(output_dir: Path, *, ask_number: Callable, print_header: Callable, print_option: Callable, c: Callable):
    providers = [output_dir / n for n in ("comix", "mangago") if (output_dir / n).is_dir()]
    if not providers:
        print(c("warning", "Nenhum provider encontrado."))
        return
    print_header("TRATAR MERGES PENDENTES")
    for i, provider in enumerate(providers, 1):
        print_option(i, provider.name.capitalize())
    print_option(0, "Voltar")
    n = ask_number("\nSelecione uma opção › ", range(0, len(providers) + 1))
    if n == 0:
        return
    provider = providers[n - 1]

    mangas = sorted([p for p in provider.iterdir() if p.is_dir()], key=_key)
    if not mangas:
        print(c("warning", "Nenhuma obra encontrada."))
        return
    print_header(provider.name.upper())
    for i, manga in enumerate(mangas, 1):
        print_option(i, manga.name)
    print_option(0, "Voltar")
    n = ask_number("\nSelecione uma opção › ", range(0, len(mangas) + 1))
    if n == 0:
        return
    manga = mangas[n - 1]

    selected = _choose_review_chapters(manga, ask_number, print_header, print_option, c)
    if not selected:
        return

    while True:
        print_header("CAPÍTULOS PARA TRATATIVA")
        for i, chapter in enumerate(selected, 1):
            official = _official_valid(manga, chapter.name)
            has_review = (_review(manga, chapter.name) / "merge-review.json").is_file()
            status = "MERGE" if official else "PENDENTE"
            if has_review:
                status += " · PROPOSTA"
            print(
                f"  {c('number', str(i)+'.', bold=True)} "
                f"{chapter.name:<32} "
                f"{c('success' if official else 'warning', status)}"
            )
        print(f"  {c('number', '0.', bold=True)} Voltar")
        n = ask_number("\nSelecione um capítulo › ", range(0, len(selected) + 1))
        if n == 0:
            return
        _run_chapter_review(
            manga, selected[n - 1],
            ask_number, print_header, print_option, c
        )

