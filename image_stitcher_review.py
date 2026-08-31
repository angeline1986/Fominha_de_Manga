#!/usr/bin/env python3
"""Exception-review flow for the frozen Merge V3."""
from __future__ import annotations
import json, re, shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from PIL import Image
import image_stitcher as v3

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
            if not safe:
                return None, proposal, (
                    "Sem faixa branca V3 >=150 px até "
                    f"{REVIEW_MAX:,} px após o último corte. Requer análise específica."
                )
            chosen, strategy = safe[0], "strict_small_extension"

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
    oversized = [(a,b,b-a) for a,b in zip(bounds,bounds[1:]) if b-a > REVIEW_MAX]
    if oversized:
        a,b,size = oversized[0]
        return None, proposal, f"Proposta ainda contém trecho de {size:,} px ({a:,}–{b:,})."
    return cuts, proposal, None

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

def generate_candidate(manga, chapter):
    pages=v3.list_pages(chapter)
    infos,bands,total,_=v3.analyze_chapter(
        pages, sample_width=v3.DEFAULT_SAMPLE_WIDTH,
        light_threshold=v3.DEFAULT_LIGHT_THRESHOLD,
        white_ratio_threshold=v3.DEFAULT_WHITE_RATIO,
    )
    cuts,proposal,error=build_proposal(total,infos,bands)
    if error: return False,error,None
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
                  "review_max_chunk_height":REVIEW_MAX,"small_extension_limit":EXTRA_LIMIT},
    }
    (dest/"merge-review.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    return True,f"Proposta: {len(pages)} originais → {len(outputs)} imagens; {len(proposal)} resgate(s).",dest

def approve(manga, chapter):
    src=_review(manga,chapter); mf=src/"merge-review.json"
    if not mf.is_file(): return False,"Nenhuma proposta encontrada."
    dst=_official(manga,chapter)
    if dst.exists(): return False,"Já existe MERGE oficial para este capítulo."
    payload=json.loads(mf.read_text(encoding="utf-8"))
    outputs=sorted(src.glob("merged-*.png"),key=_key)
    if not outputs: return False,"Proposta sem imagens."
    dst.mkdir(parents=True)
    for p in outputs: shutil.copy2(p,dst/p.name)
    payload["status"]="approved"; payload["approved_at"]=datetime.now(timezone.utc).isoformat()
    payload["algorithm"]="merge_review_v1_approved"
    (dst/"merge-manifest.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    return True,f"Merge promovido para {dst}"

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

