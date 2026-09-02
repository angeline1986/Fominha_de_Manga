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
    if not m.is_file() or not v3.merge_artifact_files(d):
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

def build_proposal(total_height, infos, bands, *, terminal_max_height=None):
    cuts = _v3_from(0, total_height, bands)
    proposal = []
    current = cuts[-1]["center"] if cuts else 0

    while total_height-current > v3.DEFAULT_MAX_CHUNK_HEIGHT:
        if (
            terminal_max_height is not None
            and total_height-current <= int(terminal_max_height)
        ):
            break
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


def _uniform_band_candidates(pages, infos, sample_width=256, band_height=18, max_channel_std=7.0, max_edge_mean=10.0):
    import numpy as np
    out=[]; gy=0
    for page,info in zip(pages,infos):
        with Image.open(page) as im:
            rgb=im.convert("RGB"); w,h=rgb.size
            if h < band_height: gy += h; continue
            sw=min(sample_width,w); x0=max(0,(w-sw)//2)
            arr=np.asarray(rgb.crop((x0,0,x0+sw,h)),dtype=np.float32)
            full_arr=np.asarray(rgb,dtype=np.float32)
            step=max(4,band_height//2)
            for y in range(0,h-band_height+1,step):
                strip=arr[y:y+band_height]; flat=strip.reshape(-1,3)
                std=float(flat.std(axis=0).max())
                dx=float(np.abs(np.diff(strip,axis=1)).mean()) if strip.shape[1]>1 else 0.0
                dy=float(np.abs(np.diff(strip,axis=0)).mean()) if strip.shape[0]>1 else 0.0
                edge=max(dx,dy)

                full_strip=full_arr[y:y+band_height]
                full_flat=full_strip.reshape(-1,3)
                full_std=float(full_flat.std(axis=0).max())
                full_dx=float(np.abs(np.diff(full_strip,axis=1)).mean()) if full_strip.shape[1]>1 else 0.0
                full_dy=float(np.abs(np.diff(full_strip,axis=0)).mean()) if full_strip.shape[0]>1 else 0.0
                full_edge=max(full_dx,full_dy)

                if (
                    std<=max_channel_std
                    and edge<=max_edge_mean
                    and full_std<=max_channel_std
                    and full_edge<=max_edge_mean
                ):
                    out.append({
                        "center":int(gy+y+band_height//2),
                        "band_height":band_height,
                        "uniform_std":std,
                        "edge_mean":edge,
                        "full_width_uniform_std":full_std,
                        "full_width_edge_mean":full_edge,
                        "review_strategy":"uniform_color_safe_band",
                    })
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


def _enforce_source_limit(cuts, infos, bands, total_height, max_source_images, pages=None, uniform_candidates=None):
    limit=int(max_source_images)
    if limit<2: return None,[],"O limite mínimo é 2 imagens de origem por merge."
    centers={int(c["center"]):dict(c) for c in cuts}; inserted=[]; uniform=(list(uniform_candidates) if uniform_candidates is not None else None)
    for _ in range(10000):
        bounds=[0]+sorted(centers)+[total_height]; violation=None
        for start,end in zip(bounds,bounds[1:]):
            sources=_segment_sources(infos,start,end)
            if len(sources)>limit: violation=(start,end,sources); break
        if violation is None: return [centers[k] for k in sorted(centers)],inserted,None
        start,end,sources=violation; allowed_end=sources[limit-1].global_end
        lower=start+v3.DEFAULT_MIN_CHUNK_HEIGHT; upper=min(allowed_end,end-v3.DEFAULT_MIN_CHUNK_HEIGHT); target=start+v3.DEFAULT_TARGET_HEIGHT
        white=[]
        for b in bands:
            center=(b.start+b.end)//2
            if center in centers or not (lower<=center<=upper) or b.height<v3.DEFAULT_MIN_WHITE_BAND: continue
            page,local=v3.page_at_y(infos,center)
            white.append({"center":center,"band_height":b.height,"white_ratio_mean":b.white_ratio_mean,"page":page,"local_y":local,"review_strategy":"source_limit_safe_white_band"})
        if white:
            chosen=sorted(white,key=lambda x:(abs(x["center"]-target),-x["band_height"],-x["white_ratio_mean"],x["center"]))[0]
        else:
            if uniform is None:
                if pages is None:
                    return None,inserted,"Detector de faixa uniforme sem páginas de origem."
                uniform=_uniform_band_candidates(pages,infos)
            chosen=_choose_uniform_cut(uniform,infos,start,end,allowed_end)
            if chosen is None: return None,inserted,f"Não existe faixa branca nem faixa uniforme segura que mantenha este trecho em até {limit} imagens de origem. Aumente o máximo e regenere a proposta."
        centers[int(chosen["center"])]=chosen; inserted.append(dict(chosen))
    return None,inserted,"Limite interno atingido ao planejar os cortes."

def _render(pages, cuts, dest):
    dest.mkdir(parents=True, exist_ok=True)
    for p in v3.merge_artifact_files(dest): p.unlink()
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
        used_sources=[]
        for p,p0,p1 in spans:
            lo,hi=max(start,p0),min(end,p1)
            if hi<=lo: continue
            used_sources.append(p.name)
            with Image.open(p) as im:
                crop=im.convert("RGB").crop((0,lo-p0,width,hi-p0))
                canvas.paste(crop,(0,lo-start))
        out_name=v3.page_range_output_name_from_sources(used_sources)
        target=v3.ensure_unique_output_path(dest,out_name)
        canvas.save(target,"PNG"); outputs.append(target)
    return outputs,bounds

def _region_view(infos, bands, start, end):
    """Cria uma visão local 0..N de um intervalo global do capítulo."""
    local_infos = []

    for info in infos:
        lo = max(int(start), int(info.global_start))
        hi = min(int(end), int(info.global_end))

        if hi <= lo:
            continue

        local_infos.append(
            v3.PageInfo(
                info.path,
                info.width,
                hi - lo,
                lo - start,
                hi - start,
            )
        )

    local_bands = []

    for band in bands:
        lo = max(int(start), int(band.start))
        hi = min(int(end), int(band.end))

        if hi <= lo:
            continue

        local_bands.append(
            v3.WhiteBand(
                lo - start,
                hi - start,
                hi - lo,
                band.white_ratio_mean,
            )
        )

    return local_infos, local_bands


def _globalize_review_items(items, origin, full_infos):
    """Converte cuts/proposal locais novamente para coordenadas globais."""
    result = []

    for raw in items:
        item = dict(raw)

        for key in ("center", "band_start", "band_end"):
            if key in item:
                item[key] = int(item[key]) + int(origin)

        if "center" in item:
            page, local_y = v3.page_at_y(
                full_infos,
                int(item["center"]),
            )
            item["page"] = page
            item["local_y"] = local_y

        result.append(item)

    return result


def _normalize_pending_segments(pending_segments, total_height):
    normalized = []

    for index, raw in enumerate(pending_segments or [], 1):
        try:
            start = int(raw["global_start"])
            end = int(raw["global_end"])
        except (KeyError, TypeError, ValueError):
            return None, (
                f"Pending segment #{index} possui limites inválidos."
            )

        if start < 0 or end <= start or end > int(total_height):
            return None, (
                f"Pending segment #{index} fora da cobertura do capítulo: "
                f"{start}..{end}."
            )

        normalized.append(
            {
                "segment_id": raw.get("id", index),
                "global_start": start,
                "global_end": end,
            }
        )

    normalized.sort(
        key=lambda x: (
            x["global_start"],
            x["global_end"],
        )
    )

    previous_end = None

    for item in normalized:
        if (
            previous_end is not None
            and item["global_start"] < previous_end
        ):
            return None, (
                "Pending segments sobrepostos não são permitidos."
            )

        previous_end = item["global_end"]

    if not normalized:
        return None, "Nenhum pending segment informado para revisão."

    return normalized, None


def _render_scoped_bounds(
    infos,
    bounds,
    dest,
    output_index,
):
    """Renderiza bounds GLOBAIS diretamente das fontes originais."""
    if not infos:
        raise ValueError("Capítulo sem PageInfo para renderização.")

    width = int(infos[0].width)
    outputs = []

    for start, end in zip(bounds, bounds[1:]):
        start = int(start)
        end = int(end)

        canvas = Image.new(
            "RGB",
            (width, end - start),
            "white",
        )

        for info in infos:
            lo = max(start, int(info.global_start))
            hi = min(end, int(info.global_end))

            if hi <= lo:
                continue

            with Image.open(info.path) as im:
                rgb = im.convert("RGB")

                crop = rgb.crop(
                    (
                        0,
                        lo - int(info.global_start),
                        width,
                        hi - int(info.global_start),
                    )
                )

                canvas.paste(
                    crop,
                    (
                        0,
                        lo - start,
                    ),
                )

        used_sources = [
            info.path.name
            for info in infos
            if min(end, int(info.global_end)) > max(start, int(info.global_start))
        ]
        out_name = v3.page_range_output_name_from_sources(used_sources)
        target = v3.ensure_unique_output_path(dest, out_name)
        canvas.save(target, "PNG")

        outputs.append(target)
        output_index += 1

    return outputs, output_index


def _generate_pending_candidate(
    manga,
    chapter,
    pages,
    infos,
    bands,
    total,
    pending_segments,
    max_source_images,
):
    pending, pending_error = _normalize_pending_segments(
        pending_segments,
        total,
    )

    if pending_error:
        return False, pending_error, None

    # Uniform bands são calculadas no sistema global uma única vez.
    # Cada região recebe somente os candidatos que realmente pertencem
    # ao seu intervalo, rebaseados para 0..region_height.
    global_uniform = None

    plans = []
    all_cuts = []
    all_proposal = []
    max_used = 0

    for region_index, region in enumerate(pending, 1):
        start = int(region["global_start"])
        end = int(region["global_end"])
        region_height = end - start

        local_infos, local_bands = _region_view(
            infos,
            bands,
            start,
            end,
        )

        if not local_infos:
            return (
                False,
                f"Pending segment {start}..{end} "
                "não possui imagens de origem.",
                None,
            )

        cuts, proposal, error = build_proposal(
            region_height,
            local_infos,
            local_bands,
            terminal_max_height=REVIEW_MAX,
        )

        if error:
            return (
                False,
                f"Região {start}..{end}: {error}",
                None,
            )

        initial_bounds = (
            [0]
            + [int(c["center"]) for c in cuts]
            + [region_height]
        )

        violates_source_limit = any(
            len(_segment_sources(local_infos, a, b))
            > int(max_source_images)
            for a, b in zip(
                initial_bounds,
                initial_bounds[1:],
            )
        )

        local_uniform = None

        if violates_source_limit:
            if global_uniform is None:
                global_uniform = _uniform_band_candidates(
                    pages,
                    infos,
                )

            local_uniform = []

            for raw in global_uniform:
                center = int(raw["center"])

                if not (start <= center <= end):
                    continue

                item = dict(raw)
                item["center"] = center - start

                local_uniform.append(item)

        cuts, limit_cuts, limit_error = _enforce_source_limit(
            cuts,
            local_infos,
            local_bands,
            region_height,
            max_source_images,
            pages=None,
            uniform_candidates=local_uniform,
        )

        if limit_error:
            return (
                False,
                f"Região {start}..{end}: {limit_error}",
                None,
            )

        proposal = list(proposal) + list(limit_cuts)

        local_bounds = (
            [0]
            + [int(c["center"]) for c in cuts]
            + [region_height]
        )

        global_bounds = [
            start + int(value)
            for value in local_bounds
        ]

        global_cuts = _globalize_review_items(
            cuts,
            start,
            infos,
        )

        global_proposal = _globalize_review_items(
            proposal,
            start,
            infos,
        )

        source_pages = [
            info.path.name
            for info in infos
            if min(end, int(info.global_end))
            > max(start, int(info.global_start))
        ]

        used = max(
            (
                len(_segment_sources(local_infos, a, b))
                for a, b in zip(
                    local_bounds,
                    local_bounds[1:],
                )
            ),
            default=0,
        )

        max_used = max(max_used, used)

        plans.append(
            {
                "region_id": region_index,
                "segment_id": region["segment_id"],
                "global_start": start,
                "global_end": end,
                "boundaries": global_bounds,
                "cuts": global_cuts,
                "proposal": global_proposal,
                "source_pages": source_pages,
                "outputs": [],
            }
        )

        all_cuts.extend(global_cuts)
        all_proposal.extend(global_proposal)

    # Só tocamos no diretório de proposta depois que TODAS as regiões
    # foram planejadas com sucesso. Assim uma falha posterior não deixa
    # uma proposta parcial.
    dest = _review(manga, chapter.name)
    dest.mkdir(parents=True, exist_ok=True)

    for old in v3.merge_artifact_files(dest):
        old.unlink()

    output_index = 1
    all_outputs = []

    for plan in plans:
        outputs, output_index = _render_scoped_bounds(
            infos,
            plan["boundaries"],
            dest,
            output_index,
        )

        plan["outputs"] = [p.name for p in outputs]
        all_outputs.extend(outputs)

    scoped_page_names = []

    for info in infos:
        for region in pending:
            if (
                min(
                    int(region["global_end"]),
                    int(info.global_end),
                )
                > max(
                    int(region["global_start"]),
                    int(info.global_start),
                )
            ):
                scoped_page_names.append(info.path.name)
                break

    intervals = [
        [
            int(region["global_start"]),
            int(region["global_end"]),
        ]
        for region in pending
    ]

    manifest = {
        "schema_version": 1,
        "status": "candidate",
        "algorithm": "merge_review_v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "chapter": chapter.name,
        "source_pages": scoped_page_names,
        "proposal": all_proposal,
        "cuts": all_cuts,

        # O formato antigo só representa uma cobertura contínua.
        # Para uma única região podemos mantê-lo por compatibilidade.
        # Para múltiplas regiões, `regions` é a fonte de verdade.
        "boundaries": (
            plans[0]["boundaries"]
            if len(plans) == 1
            else []
        ),

        "outputs": [p.name for p in all_outputs],

        "scope": {
            "type": "pending_segments",
            "intervals": intervals,
        },

        "regions": plans,

        "policy": {
            "main_v3_modified": False,
            "forced_cut": False,
            "min_white_band": v3.DEFAULT_MIN_WHITE_BAND,
            "normal_max_chunk_height": (
                v3.DEFAULT_MAX_CHUNK_HEIGHT
            ),
            "review_max_chunk_height": REVIEW_MAX,
            "small_extension_limit": EXTRA_LIMIT,
            "extended_safe_zone": True,
            "extended_safe_zone_rule": (
                "first_strict_white_band_after_review_max"
            ),
            "max_source_images": int(max_source_images),
            "source_limit_rule": (
                "white_first_then_uniform_color_safe_band_"
                "within_user_limit"
            ),
            "uniform_color_fallback": "MERGE_REVIEW_ONLY",
            "pending_scope_isolated": True,
        },
    }

    (dest / "merge-review.json").write_text(
        json.dumps(
            manifest,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return (
        True,
        (
            f"Proposta: {len(scoped_page_names)} originais "
            f"em {len(plans)} região(ões) pendente(s) "
            f"→ {len(all_outputs)} merges; "
            f"máximo utilizado: "
            f"{max_used}/{int(max_source_images)} "
            "originais por merge."
        ),
        dest,
    )


def generate_candidate(
    manga,
    chapter,
    *,
    max_source_images=8,
    pending_segments=None,
):
    pages = v3.list_pages(chapter)

    infos, bands, total, _ = v3.analyze_chapter(
        pages,
        sample_width=v3.DEFAULT_SAMPLE_WIDTH,
        light_threshold=v3.DEFAULT_LIGHT_THRESHOLD,
        white_ratio_threshold=v3.DEFAULT_WHITE_RATIO,
    )

    if pending_segments is not None:
        return _generate_pending_candidate(
            manga,
            chapter,
            pages,
            infos,
            bands,
            total,
            pending_segments,
            max_source_images,
        )

    # --------------------------------------------------------------
    # Caminho histórico M2/M3: permanece funcionalmente inalterado.
    # --------------------------------------------------------------
    cuts, proposal, error = build_proposal(
        total,
        infos,
        bands,
    )

    if error:
        return False, error, None

    cuts, limit_cuts, limit_error = _enforce_source_limit(
        cuts,
        infos,
        bands,
        total,
        max_source_images,
        pages=pages,
    )

    if limit_error:
        return False, limit_error, None

    proposal = list(proposal) + list(limit_cuts)

    dest = _review(manga, chapter.name)
    outputs, bounds = _render(
        pages,
        cuts,
        dest,
    )

    manifest = {
        "schema_version": 1,
        "status": "candidate",
        "algorithm": "merge_review_v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "chapter": chapter.name,
        "source_pages": [p.name for p in pages],
        "proposal": proposal,
        "cuts": cuts,
        "boundaries": bounds,
        "outputs": [p.name for p in outputs],
        "policy": {
            "main_v3_modified": False,
            "forced_cut": False,
            "min_white_band": v3.DEFAULT_MIN_WHITE_BAND,
            "normal_max_chunk_height": (
                v3.DEFAULT_MAX_CHUNK_HEIGHT
            ),
            "review_max_chunk_height": REVIEW_MAX,
            "small_extension_limit": EXTRA_LIMIT,
            "extended_safe_zone": True,
            "extended_safe_zone_rule": (
                "first_strict_white_band_after_review_max"
            ),
            "max_source_images": int(max_source_images),
            "source_limit_rule": (
                "white_first_then_uniform_color_safe_band_"
                "within_user_limit"
            ),
            "uniform_color_fallback": "MERGE_REVIEW_ONLY",
        },
    }

    (dest / "merge-review.json").write_text(
        json.dumps(
            manifest,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    max_used = max(
        (
            len(_segment_sources(infos, a, b))
            for a, b in zip(
                bounds,
                bounds[1:],
            )
        ),
        default=0,
    )

    return (
        True,
        (
            f"Proposta: {len(pages)} originais "
            f"→ {len(outputs)} merges; "
            f"máximo utilizado: "
            f"{max_used}/{int(max_source_images)} "
            "originais por merge."
        ),
        dest,
    )

def _approve_scoped_level2_review(
    manga,
    chapter,
    review_dir,
    review_payload,
):
    """Compose Level II PASSED artifacts with scoped Review outputs."""
    manga = Path(manga)
    chapter_name = str(chapter)

    auto_dir = manga / SECONDARY / "AUTO_MERGE" / chapter_name
    auto_manifest_path = auto_dir / "auto-merge-manifest.json"
    if not auto_manifest_path.is_file():
        return False, f"Manifesto Auto-Merge não encontrado: {auto_manifest_path}"
    try:
        auto_payload = json.loads(auto_manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return False, f"Manifesto Auto-Merge inválido: {exc}"
    if auto_payload.get("algorithm") != "auto_merge_level1_resolved_segments":
        return False, "Manifesto Auto-Merge possui algoritmo não suportado para Review scoped."

    level2_dir = (
        manga
        / SECONDARY
        / "MERGE_LEVEL2"
        / chapter_name
    )
    level2_manifest_path = (
        level2_dir / "merge-level2-manifest.json"
    )

    if not level2_manifest_path.is_file():
        return False, (
            "Manifesto Level II não encontrado para aprovação scoped: "
            f"{level2_manifest_path}"
        )

    try:
        level2_payload = json.loads(
            level2_manifest_path.read_text(
                encoding="utf-8"
            )
        )
    except Exception as exc:
        return False, f"Manifesto Level II inválido: {exc}"
    if level2_payload.get("algorithm") != "merge_level2_residual_v2":
        return False, "Manifesto Level II possui algoritmo não suportado para Review scoped."

    try:
        total_height = int(
            level2_payload["total_height"]
        )
    except (KeyError, TypeError, ValueError):
        return False, (
            "Manifesto Level II sem total_height válido."
        )

    if total_height <= 0:
        return False, (
            "total_height do Level II deve ser positivo."
        )

    level3_dir = (
        manga
        / SECONDARY
        / "MERGE_LEVEL3"
        / chapter_name
    )
    level3_manifest_path = (
        level3_dir / "merge-level3-manifest.json"
    )
    level3_payload = None
    if level3_manifest_path.is_file():
        try:
            level3_payload = json.loads(
                level3_manifest_path.read_text(encoding="utf-8")
            )
        except Exception as exc:
            return False, f"Manifesto Level III inválido: {exc}"

        if (
            level3_payload.get("algorithm")
            != "merge_level3_structural_safe_v1"
        ):
            return False, (
                "Manifesto Level III possui algoritmo não suportado."
            )
        try:
            level3_total = int(level3_payload["total_height"])
        except (KeyError, TypeError, ValueError):
            return False, "Manifesto Level III sem total_height válido."
        if level3_total != total_height:
            return False, (
                "Manifesto Level III não corresponde ao total_height "
                "do Level II atual."
            )

        import hashlib
        expected_level2_sha256 = hashlib.sha256(
            level2_manifest_path.read_bytes()
        ).hexdigest()
        if (
            str(level3_payload.get("source_level2_sha256") or "")
            != expected_level2_sha256
        ):
            return False, (
                "Manifesto Level III está desatualizado em relação "
                "ao manifesto Level II atual."
            )

    # O Review scoped deve representar a autoridade pendente atual.
    scope = review_payload.get("scope") or {}
    if scope.get("type") != "pending_segments":
        return False, (
            "Review scoped possui tipo de scope inválido."
        )

    try:
        level2_pending_intervals = sorted(
            (
                int(item["global_start"]),
                int(item["global_end"]),
            )
            for item in (
                level2_payload.get("pending_segments") or []
            )
        )
        review_scope_intervals = sorted(
            (
                int(item[0]),
                int(item[1]),
            )
            for item in (
                scope.get("intervals") or []
            )
        )
        review_region_intervals = sorted(
            (
                int(item["global_start"]),
                int(item["global_end"]),
            )
            for item in (
                review_payload.get("regions") or []
            )
        )
    except (
        KeyError,
        TypeError,
        ValueError,
        IndexError,
    ):
        return False, (
            "Review/Level II possuem intervalos scoped inválidos."
        )

    if not level2_pending_intervals:
        return False, (
            "Level II não possui segmentos pendentes "
            "para composição scoped."
        )

    authoritative_pending = level2_pending_intervals

    if level3_payload is not None:
        try:
            level3_safe_intervals = sorted(
                (
                    int(item["global_start"]),
                    int(item["global_end"]),
                )
                for item in (
                    level3_payload.get("safe_artifacts") or []
                )
            )
            level3_residual_intervals = sorted(
                (
                    int(item["global_start"]),
                    int(item["global_end"]),
                )
                for item in (
                    level3_payload.get("residual_pending_segments") or []
                )
            )
        except (KeyError, TypeError, ValueError):
            return False, "Level III possui intervalos inválidos."

        children = sorted(
            level3_safe_intervals + level3_residual_intervals
        )
        child_index = 0
        for parent_start, parent_end in level2_pending_intervals:
            if parent_end <= parent_start:
                return False, "Level II possui pending interval inválido."
            cursor = parent_start
            while (
                child_index < len(children)
                and children[child_index][0] < parent_end
            ):
                child_start, child_end = children[child_index]
                if (
                    child_start != cursor
                    or child_end <= child_start
                    or child_end > parent_end
                ):
                    return False, (
                        "Level III não recompõe exatamente o pending "
                        "do Level II (GAP/OVERLAP)."
                    )
                cursor = child_end
                child_index += 1
            if cursor != parent_end:
                return False, (
                    "Level III não recompõe exatamente o pending "
                    "do Level II (cobertura incompleta)."
                )
        if child_index != len(children):
            return False, (
                "Level III possui intervalo fora do pending do Level II."
            )

        authoritative_pending = level3_residual_intervals
        if not authoritative_pending:
            return False, (
                "Level III não possui residual pendente; "
                "Review scoped não deve ser aprovado."
            )

    if review_scope_intervals != authoritative_pending:
        return False, (
            "Review scoped está desatualizado: scope.intervals não "
            "corresponde ao pending autoritativo atual."
        )
    if review_region_intervals != authoritative_pending:
        return False, (
            "Review scoped está inconsistente: regions não corresponde "
            "ao pending autoritativo atual."
        )

    pieces = []

    # Auto-Merge Level I: artefatos resolvidos e persistidos na origem.
    for artifact in auto_payload.get("artifacts") or []:
        try:
            start=int(artifact["global_start"]); end=int(artifact["global_end"])
        except (KeyError,TypeError,ValueError):
            return False,"Artefato Auto-Merge possui intervalo inválido."
        filename=str(artifact.get("file") or "").strip()
        if not filename: return False,"Artefato Auto-Merge não possui arquivo."
        pieces.append({"kind":"auto_merge","source":auto_dir/filename,"source_file":filename,"global_start":start,"global_end":end})

    # Level II: somente artefatos realmente resolvidos pelo próprio Level II.
    for artifact in level2_payload.get("artifacts") or []:
        try:
            start=int(artifact["global_start"]); end=int(artifact["global_end"])
        except (KeyError,TypeError,ValueError):
            return False,"Artefato Level II possui intervalo inválido."
        filename=str(artifact.get("file") or "").strip()
        if not filename: return False,"Artefato Level II não possui arquivo."
        pieces.append({"kind":"level2","source":level2_dir/filename,"source_file":filename,"global_start":start,"global_end":end})

    # Level III: artefatos SAFE materializados sobre o pending do Level II.
    if level3_payload is not None:
        for artifact in level3_payload.get("safe_artifacts") or []:
            try:
                start = int(artifact["global_start"])
                end = int(artifact["global_end"])
            except (KeyError, TypeError, ValueError):
                return False, (
                    "Artefato SAFE do Level III possui intervalo inválido."
                )
            filename = str(artifact.get("file") or "").strip()
            if not filename:
                return False, (
                    "Artefato SAFE do Level III não possui arquivo."
                )
            pieces.append(
                {
                    "kind": "level3",
                    "source": level3_dir / filename,
                    "source_file": filename,
                    "global_start": start,
                    "global_end": end,
                }
            )

    # Review scoped: regions é a fonte de verdade.
    regions = review_payload.get("regions") or []

    if not regions:
        return False, (
            "Review scoped não possui regions."
        )

    for region in regions:
        try:
            region_start = int(
                region["global_start"]
            )
            region_end = int(
                region["global_end"]
            )
            boundaries = [
                int(value)
                for value in (
                    region.get("boundaries") or []
                )
            ]
        except (KeyError, TypeError, ValueError):
            return False, (
                "Região Review possui "
                "intervalo/boundaries inválidos."
            )

        filenames = [
            str(value)
            for value in (
                region.get("outputs") or []
            )
        ]

        if (
            len(boundaries) < 2
            or boundaries[0] != region_start
            or boundaries[-1] != region_end
        ):
            return False, (
                "Boundaries do Review não correspondem "
                "ao intervalo global da região."
            )

        if len(filenames) != len(boundaries) - 1:
            return False, (
                "Quantidade de outputs do Review não "
                "corresponde aos boundaries da região."
            )

        for filename, start, end in zip(
            filenames,
            boundaries,
            boundaries[1:],
        ):
            pieces.append(
                {
                    "kind": "review",
                    "source": review_dir / filename,
                    "source_file": filename,
                    "global_start": int(start),
                    "global_end": int(end),
                }
            )

    if not pieces:
        return False, (
            "Nenhum artefato disponível "
            "para composição final."
        )

    pieces.sort(
        key=lambda item: (
            item["global_start"],
            item["global_end"],
            item["kind"],
            item["source_file"],
        )
    )

    # Fail-before-write.
    expected_start = 0
    expected_width = None

    for piece in pieces:
        start = piece["global_start"]
        end = piece["global_end"]
        source = piece["source"]

        if end <= start:
            return False, (
                "Intervalo inválido na composição final: "
                f"{start}..{end}."
            )

        if start > expected_start:
            return False, (
                "Composição final possui GAP: "
                f"esperado início {expected_start}, "
                f"encontrado {start}."
            )

        if start < expected_start:
            return False, (
                "Composição final possui OVERLAP: "
                f"esperado início {expected_start}, "
                f"encontrado {start}."
            )

        if not source.is_file():
            return False, (
                "Artefato ausente na composição final: "
                f"{source}"
            )

        try:
            with Image.open(source) as image:
                width, height = image.size
                image.verify()
        except Exception as exc:
            return False, (
                "Artefato inválido na composição final "
                f"({source.name}): {exc}"
            )

        expected_height = end - start

        if int(height) != expected_height:
            return False, (
                f"Altura incompatível em {source.name}: "
                f"{height} != {expected_height}."
            )

        if expected_width is None:
            expected_width = int(width)
        elif int(width) != expected_width:
            return False, (
                f"Largura incompatível em {source.name}: "
                f"{width} != {expected_width}."
            )

        expected_start = end

    if expected_start != total_height:
        return False, (
            "Cobertura final incompleta: "
            f"{expected_start} != {total_height}."
        )

    official_dir = _official(
        manga,
        chapter_name,
    )

    # Só chegamos aqui após validar TODOS os artefatos.
    if official_dir.exists():
        if v3.is_chapter_merged(
            manga / "IMG" / chapter_name
        ):
            return False, (
                "Já existe MERGE oficial válido "
                "para este capítulo."
            )

        stale_manifest = (
            official_dir / "merge-manifest.json"
        )
        stale_review_promotion = False

        if stale_manifest.is_file():
            try:
                stale_payload = json.loads(
                    stale_manifest.read_text(
                        encoding="utf-8"
                    )
                )
                stale_review_promotion = (
                    stale_payload.get("algorithm")
                    == "merge_review_v1_approved"
                )
            except Exception:
                stale_review_promotion = False

        if not stale_review_promotion:
            return False, (
                "Já existe MERGE oficial não reconhecido; "
                "promoção cancelada por segurança."
            )

        shutil.rmtree(official_dir)

    official_dir.mkdir(
        parents=True,
        exist_ok=False,
    )

    outputs = []

    try:
        for index, piece in enumerate(
            pieces,
            1,
        ):
            filename = piece["source"].name
            destination = v3.ensure_unique_output_path(
                official_dir, filename
            )

            # Preserva exatamente os bytes do artefato.
            shutil.copy2(
                piece["source"],
                destination,
            )

            outputs.append(
                {
                    "file": filename,
                    "global_start": (
                        piece["global_start"]
                    ),
                    "global_end": (
                        piece["global_end"]
                    ),
                    "width": expected_width,
                    "height": (
                        piece["global_end"]
                        - piece["global_start"]
                    ),
                    "sources": [],
                    "source_stage": piece["kind"],
                    "source_file": (
                        piece["source_file"]
                    ),
                }
            )

        manifest = {
            "schema_version": 1,
            "algorithm": (
                "merge_auto_level2_level3_review_composition_v2"
                if level3_payload is not None
                else "merge_auto_level2_review_composition_v2"
            ),
            "status": "approved",
            "approved_at": datetime.now(
                timezone.utc
            ).isoformat(),
            "source_dir": str(
                manga / "IMG" / chapter_name
            ),
            "output_dir": str(
                official_dir
            ),
            "source_width": int(
                expected_width or 0
            ),
            "source_total_height": (
                total_height
            ),
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
                "review_artifacts_rerendered": False,
            },
            "composition": {
                "auto_merge_manifest": "auto-merge-manifest.json",
                "level2_manifest": (
                    "merge-level2-manifest.json"
                ),
                "level3_manifest": (
                    "merge-level3-manifest.json"
                    if level3_payload is not None
                    else None
                ),
                "review_manifest": (
                    "merge-review.json"
                ),
                "scope": (
                    review_payload.get("scope")
                ),
            },
        }

        (
            official_dir / "merge-manifest.json"
        ).write_text(
            json.dumps(
                manifest,
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        chapter_dir = (
            manga / "IMG" / chapter_name
        )

        if not v3.is_chapter_merged(
            chapter_dir
        ):
            raise RuntimeError(
                "MERGE composto não foi reconhecido "
                "como oficial."
            )

    except Exception as exc:
        if official_dir.is_dir():
            shutil.rmtree(
                official_dir
            )

        return False, (
            "Falha ao materializar "
            f"composição final: {exc}"
        )

    return True, (
        "Merge composto e validado em "
        f"{official_dir}"
    )


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
    scope=payload.get("scope") or {}
    scope_type=scope.get("type")

    if scope_type=="pending_segments":
        return _approve_scoped_level2_review(
            manga,
            chapter,
            src,
            payload,
        )

    # Reviews históricos não possuem scope.
    #
    # Se houver scope, mas ele não for o contrato scoped atual,
    # não podemos tratá-lo silenciosamente como Review histórico.
    # Isso inclui propostas legadas geradas antes da formalização
    # de pending_segments/regions.
    if scope:
        return False,(
            "Proposta Review utiliza scope não suportado "
            f"({scope_type!r}); regenere a proposta antes de aprovar."
        )

    outputs=v3.merge_artifact_files(src)
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

