from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image
import numpy as np

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
BALANCE_RATIO = 0.50


def _secondary(manga: Path) -> Path:
    return manga / "FLUXO_SECUNDARIO"


def _merge_root(manga: Path) -> Path:
    return _secondary(manga) / "02_MERGE"


def _validation_root(manga: Path) -> Path:
    return _secondary(manga) / "01_MERGE_PROCESSAMENTO" / "BALANCE_VALIDATION"


def _natural_key(value: str):
    import re
    return [int(x) if x.isdigit() else x.lower() for x in re.split(r"(\d+)", value)]


def _image_height(path: Path) -> int:
    with Image.open(path) as im:
        return int(im.height)


def _chapter_analysis(chapter_dir: Path) -> dict[str, Any]:
    files = sorted(
        (p for p in chapter_dir.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTS),
        key=lambda p: _natural_key(p.name),
    )
    merges = []
    for path in files:
        try:
            height = _image_height(path)
        except Exception as exc:
            merges.append({
                "file": path.name,
                "height": None,
                "status": "ERRO",
                "reason": f"Não foi possível ler a imagem: {exc}",
            })
            continue
        merges.append({
            "file": path.name,
            "height": height,
            "status": "OK",
            "reason": "",
        })

    issues = []
    # Primeiro e último merge são deliberadamente excluídos da regra.
    for idx in range(1, len(merges) - 1):
        current = merges[idx]
        prev = merges[idx - 1]
        nxt = merges[idx + 1]
        if not all(isinstance(x.get("height"), int) and x["height"] > 0 for x in (prev, current, nxt)):
            continue
        neighbor_mean = (prev["height"] + nxt["height"]) / 2.0
        ratio = current["height"] / neighbor_mean if neighbor_mean else 1.0
        if ratio < BALANCE_RATIO:
            current["status"] = "DESBALANCEADO"
            current["neighbor_mean"] = round(neighbor_mean, 2)
            current["ratio_to_neighbors"] = round(ratio, 4)
            current["reason"] = "Altura inferior a 50% da média dos dois merges vizinhos."
            issues.append({
                "index": idx,
                "file": current["file"],
                "height": current["height"],
                "previous_file": prev["file"],
                "previous_height": prev["height"],
                "next_file": nxt["file"],
                "next_height": nxt["height"],
                "neighbor_mean": round(neighbor_mean, 2),
                "ratio_to_neighbors": round(ratio, 4),
                "threshold": BALANCE_RATIO,
            })

    status = "DESBALANCEADO" if issues else "BALANCEADO"
    return {
        "chapter": chapter_dir.name,
        "status": status,
        "merge_count": len(merges),
        "issues_count": len(issues),
        "merges": merges,
        "issues": issues,
    }


def _write_manifest(manga: Path, result: dict[str, Any]) -> None:
    target = _validation_root(manga) / str(result["chapter"])
    target.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "balance_validation_v1",
        "rule": {
            "type": "internal_merge_vs_neighbor_mean",
            "threshold_ratio": BALANCE_RATIO,
            "ignore_first_merge": True,
            "ignore_last_merge": True,
        },
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        **result,
    }
    (target / "balance-validation-manifest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )



def _proposal_root(manga: Path) -> Path:
    return _secondary(manga) / "01_MERGE_PROCESSAMENTO" / "BALANCE_PROPOSALS"


def _balance_status_root(manga: Path) -> Path:
    return _secondary(manga) / "01_MERGE_PROCESSAMENTO" / "BALANCE_STATUS"


def _merge_manifest(manga: Path, chapter: str) -> dict[str, Any]:
    path = _merge_root(manga) / str(chapter) / "merge-manifest.json"
    if not path.is_file():
        raise ValueError(f"Manifesto final ausente no cap. {chapter}.")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"Manifesto final inválido no cap. {chapter}: {exc}") from exc
    if not isinstance(data.get("outputs"), list):
        raise ValueError(f"Manifesto final sem outputs no cap. {chapter}.")
    return data


def _source_files(manga: Path, chapter: str) -> list[Path]:
    src = manga / "IMG" / str(chapter)
    if not src.is_dir():
        raise ValueError(f"Pasta IMG ausente no cap. {chapter}.")
    files = sorted(
        (
            p for p in src.iterdir()
            if p.is_file()
            and p.suffix.lower() in IMAGE_EXTS
            and not p.stem.lower().endswith("_old")
        ),
        key=lambda p: _natural_key(p.name),
    )
    if not files:
        raise ValueError(f"Nenhuma imagem ativa encontrada no cap. {chapter}.")
    return files


def _load_global_region(
    manga: Path,
    chapter: str,
    global_start: int,
    global_end: int,
    *,
    mode: str,
) -> Image.Image:
    if global_end <= global_start:
        raise ValueError("Região global inválida.")

    pieces = []
    cursor = 0
    for path in _source_files(manga, chapter):
        with Image.open(path) as im:
            height = int(im.height)
            item_start = cursor
            item_end = cursor + height
            cursor = item_end

            overlap_start = max(global_start, item_start)
            overlap_end = min(global_end, item_end)
            if overlap_end <= overlap_start:
                continue

            top = overlap_start - item_start
            bottom = overlap_end - item_start
            pieces.append(im.crop((0, top, im.width, bottom)).convert(mode))

        if cursor >= global_end:
            break

    if not pieces:
        raise ValueError("Região solicitada não intersecta as imagens-fonte.")

    width = pieces[0].width
    if any(piece.width != width for piece in pieces):
        raise ValueError("As imagens-fonte da região possuem larguras divergentes.")

    canvas = Image.new(mode, (width, sum(piece.height for piece in pieces)))
    y = 0
    for piece in pieces:
        canvas.paste(piece, (0, y))
        y += piece.height

    expected = global_end - global_start
    if canvas.height != expected:
        raise ValueError(f"Altura reconstruída divergente: {canvas.height} != {expected}.")
    return canvas


def _enumerate_safe_candidates(
    gray: np.ndarray,
    *,
    target_y: int,
    region_start: int,
    region_end: int,
):
    from processamento.unificacao_imagens.image_stitcher_level3 import (
        Level3Config,
        Level3Decision,
        Level3PendingRegion,
        analyze_structural_candidate,
    )

    cfg = Level3Config()
    region = Level3PendingRegion(
        global_start=int(region_start),
        global_end=int(region_end),
    )
    radius = max(0, int(cfg.local_search_radius))
    step = max(1, int(cfg.local_search_step))
    lower = max(int(region_start), int(target_y) - radius)
    upper = min(int(region_end) - 1, int(target_y) + radius)

    safe = []
    evaluated = 0
    for y in range(lower, upper + 1, step):
        evaluated += 1
        result = analyze_structural_candidate(
            gray,
            candidate_y=int(y),
            region=region,
            image_global_start=int(region_start),
            config=cfg,
        )
        if result.decision == Level3Decision.SAFE:
            safe.append(result)

    return safe, {
        "lower": lower,
        "upper": upper,
        "evaluated": evaluated,
        "radius": radius,
        "step": step,
    }


def _latest_proposal(manga: Path, chapter: str) -> dict[str, Any] | None:
    status_file = _balance_status_root(manga) / str(chapter) / "balance-status.json"
    if not status_file.is_file():
        return None
    try:
        status = json.loads(status_file.read_text(encoding="utf-8"))
    except Exception:
        return None

    rel = status.get("proposal_manifest")
    if not rel:
        return None
    proposal_file = _secondary(manga) / str(rel)
    if not proposal_file.is_file():
        return None

    try:
        proposal = json.loads(proposal_file.read_text(encoding="utf-8"))
    except Exception:
        return None

    return {
        "proposal_id": proposal.get("proposal_id"),
        "status": proposal.get("status"),
        "generated_at": proposal.get("generated_at"),
        "schema": proposal.get("schema"),
        "selected_files": proposal.get("selected_files") or [],
        "region": proposal.get("region"),
        "source_slices": proposal.get("source_slices") or [],
        "source_preview": proposal.get("source_preview"),
        "target_height": proposal.get("target_height"),
        "cuts": proposal.get("cuts") or [],
        "artifacts": proposal.get("artifacts") or [],
        "message": proposal.get("message") or "",
    }


def _persist_balance_proposal(manga: Path, chapter: str, payload: dict[str, Any]) -> None:
    proposal_id = str(payload["proposal_id"])
    proposal_dir = _proposal_root(manga) / chapter / proposal_id
    proposal_dir.mkdir(parents=True, exist_ok=True)
    proposal_file = proposal_dir / "balance-proposal-manifest.json"
    proposal_file.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    status_dir = _balance_status_root(manga) / chapter
    status_dir.mkdir(parents=True, exist_ok=True)
    rel = proposal_file.relative_to(_secondary(manga))
    (status_dir / "balance-status.json").write_text(
        json.dumps(
            {
                "schema": "balance_status_v1",
                "chapter": chapter,
                "status": payload["status"],
                "proposal_id": proposal_id,
                "proposal_manifest": str(rel),
                "updated_at": payload["generated_at"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _collect_global_safe_candidates(
    gray: np.ndarray,
    *,
    region_start: int,
    region_end: int,
    ideal_targets: list[int],
) -> tuple[list[Any], dict[str, Any]]:
    if region_end <= region_start:
        return [], {
            "strategy": "global_window_sweep_v1",
            "safe_candidates": 0,
            "windows": 0,
            "evaluated": 0,
        }

    probe_target = int(ideal_targets[0]) if ideal_targets else int((region_start + region_end) // 2)
    probe_safe, probe_scan = _enumerate_safe_candidates(
        gray,
        target_y=probe_target,
        region_start=region_start,
        region_end=region_end,
    )
    radius = max(1, int(probe_scan.get("radius") or 200))
    step = max(1, int(probe_scan.get("step") or 1))

    stride = max(1, radius * 2)
    first_center = region_start + radius
    last_center = region_end - radius

    centers = {int(x) for x in ideal_targets if region_start < int(x) < region_end}
    centers.add(probe_target)

    if first_center <= last_center:
        center = first_center
        while center <= last_center:
            centers.add(int(center))
            if step > 1 and center + 1 <= last_center:
                centers.add(int(center + 1))
            center += stride
        centers.add(int(last_center))
        if step > 1 and last_center - 1 >= first_center:
            centers.add(int(last_center - 1))
    else:
        centers.add(int((region_start + region_end) // 2))

    safe_by_y: dict[int, Any] = {}
    evaluated = 0
    windows = 0

    for center in sorted(centers):
        if not (region_start < center < region_end):
            continue
        safe, scan = _enumerate_safe_candidates(
            gray,
            target_y=int(center),
            region_start=region_start,
            region_end=region_end,
        )
        windows += 1
        evaluated += int(scan.get("evaluated") or 0)
        for result in safe:
            y = int(result.candidate_y)
            if region_start < y < region_end:
                safe_by_y[y] = result

    for result in probe_safe:
        y = int(result.candidate_y)
        if region_start < y < region_end:
            safe_by_y[y] = result

    results = [safe_by_y[y] for y in sorted(safe_by_y)]
    return results, {
        "strategy": "global_window_sweep_v1",
        "region_start": region_start,
        "region_end": region_end,
        "radius": radius,
        "step": step,
        "stride": stride,
        "windows": windows,
        "evaluated": evaluated,
        "safe_candidates": len(results),
    }


def _best_balanced_safe_composition(
    safe_results: list[Any],
    *,
    region_start: int,
    region_end: int,
    count: int,
) -> tuple[list[int] | None, list[Any], dict[str, Any]]:
    """
    Balanceamento v11:
    - pixels SAFE consecutivos representam UMA zona lógica de separação;
    - impede segmentos internos menores que 50% da altura-alvo;
    - segurança estrutural continua sendo pré-condição;
    - equilíbrio é usado somente entre zonas já consideradas seguras.
    """
    if count < 2:
        return [], [], {"reason": "single_chunk"}

    required_cuts = count - 1
    by_y = {int(item.candidate_y): item for item in safe_results}
    positions = sorted(y for y in by_y if region_start < y < region_end)

    if not positions:
        return None, [], {
            "reason": "insufficient_safe_candidates",
            "required_cuts": required_cuts,
            "safe_candidates": 0,
            "safe_zones": 0,
        }

    zones: list[list[int]] = []
    current = [positions[0]]
    for y in positions[1:]:
        if y - current[-1] <= 2:
            current.append(y)
        else:
            zones.append(current)
            current = [y]
    zones.append(current)

    representatives: list[int] = []
    for zone in zones:
        center = (zone[0] + zone[-1]) / 2.0
        representative = min(
            zone,
            key=lambda y: (
                abs(y - center),
                float(by_y[y].metrics.get("edge_density", 1.0)),
                int(by_y[y].metrics.get("crossing_components", 999999)),
                y,
            ),
        )
        representatives.append(representative)

    if len(representatives) < required_cuts:
        return None, [], {
            "reason": "insufficient_safe_zones",
            "required_cuts": required_cuts,
            "safe_candidates": len(positions),
            "safe_zones": len(representatives),
        }

    target = (region_end - region_start) / float(count)
    min_chunk_height = target * 0.50

    candidate_sets: list[list[int]] = []
    for ordinal in range(1, count):
        ideal = region_start + target * ordinal
        ranked = sorted(
            representatives,
            key=lambda y: (
                abs(y - ideal),
                float(by_y[y].metrics.get("edge_density", 1.0)),
                int(by_y[y].metrics.get("crossing_components", 999999)),
                y,
            ),
        )
        candidate_sets.append(ranked)

    beam: list[tuple[float, list[int]]] = [(0.0, [region_start])]
    beam_width = 400

    for ordinal, candidates in enumerate(candidate_sets, start=1):
        expanded: list[tuple[float, list[int]]] = []
        for score, path in beam:
            prev = path[-1]
            for y in candidates:
                if y <= prev or y >= region_end:
                    continue
                height = y - prev
                if height < min_chunk_height:
                    continue
                deviation = (height - target) / max(1.0, target)
                positional = abs(y - (region_start + target * ordinal)) / max(1.0, target)
                result = by_y[y]
                structural = (
                    float(result.metrics.get("edge_density", 0.0)) * 1e-3
                    + int(result.metrics.get("crossing_components", 0)) * 1e-6
                )
                new_score = score + deviation * deviation + positional * positional * 0.10 + structural
                expanded.append((new_score, [*path, y]))

        if not expanded:
            return None, [], {
                "reason": "no_complete_ordered_path",
                "required_cuts": required_cuts,
                "safe_candidates": len(positions),
                "safe_zones": len(representatives),
                "failed_ordinal": ordinal,
                "min_chunk_height": round(min_chunk_height, 2),
            }

        expanded.sort(key=lambda item: (item[0], item[1]))
        beam = expanded[:beam_width]

    finals: list[tuple[float, list[int], list[int]]] = []
    for score, path in beam:
        boundaries = [*path, region_end]
        heights = [b - a for a, b in zip(boundaries, boundaries[1:])]
        if any(h <= 0 for h in heights):
            continue
        if any(h < min_chunk_height for h in heights):
            continue
        mean_h = sum(heights) / float(len(heights))
        variance = sum((h - mean_h) ** 2 for h in heights) / float(len(heights))
        final_score = score + variance / max(1.0, mean_h * mean_h)
        finals.append((final_score, path, heights))

    if not finals:
        return None, [], {
            "reason": "no_complete_path",
            "required_cuts": required_cuts,
            "safe_candidates": len(positions),
            "safe_zones": len(representatives),
            "min_chunk_height": round(min_chunk_height, 2),
        }

    finals.sort(key=lambda item: (item[0], item[1]))
    best_score, best_path, heights = finals[0]
    cuts = best_path[1:]
    selected_results = [by_y[y] for y in cuts]

    return cuts, selected_results, {
        "reason": "best_visual_zone_balance",
        "score": round(float(best_score), 8),
        "target_height": round(float(target), 2),
        "heights": heights,
        "spread": max(heights) - min(heights),
        "safe_candidates": len(positions),
        "safe_zones": len(representatives),
        "beam_width": beam_width,
        "min_chunk_height": round(min_chunk_height, 2),
        "candidate_model": "logical_safe_zones",
    }


def _filter_balloon_crossing_candidates(
    safe_results: list[Any],
    *,
    manga: Path,
    chapter: str,
    region_start: int,
    region_end: int,
    margin_px: int = 16,
) -> tuple[list[Any], dict[str, Any]]:
    """Camada visual exclusiva do Efetuar Balanceamento."""
    try:
        from processamento.limpeza_baloes.bubble_cleaner import resolve_model, detect_regions
        rgb_image = _load_global_region(manga, chapter, region_start, region_end, mode="RGB")
        rgb = np.asarray(rgb_image, dtype=np.uint8)
        model_path = resolve_model(None)
        detections = detect_regions(rgb, model_path, conf=0.55)
    except Exception as exc:
        return [], {
            "strategy": "manga_bubble_yolo_v1",
            "ok": False,
            "reason": f"{type(exc).__name__}: {exc}",
            "detections": 0,
            "rejected_candidates": len(safe_results),
            "remaining_candidates": 0,
            "margin_px": int(margin_px),
        }

    protected_ranges: list[tuple[int, int]] = []
    for detection in detections:
        y1 = region_start + int(detection.y1) - int(margin_px)
        y2 = region_start + int(detection.y2) + int(margin_px)
        protected_ranges.append((max(region_start, y1), min(region_end, y2)))

    kept = []
    rejected = 0
    for result in safe_results:
        y = int(result.candidate_y)
        if any(y1 <= y <= y2 for y1, y2 in protected_ranges):
            rejected += 1
            continue
        kept.append(result)

    return kept, {
        "strategy": "manga_bubble_yolo_v1",
        "ok": True,
        "detections": len(detections),
        "protected_ranges": len(protected_ranges),
        "rejected_candidates": rejected,
        "remaining_candidates": len(kept),
        "margin_px": int(margin_px),
    }


def generate_balance_proposal(
    manga: Path,
    chapter: str,
    selected_files: list[str],
) -> dict[str, Any]:
    chapter = str(chapter)
    selected_names = [str(x) for x in selected_files if str(x).strip()]
    if len(selected_names) < 2:
        raise ValueError("Selecione pelo menos 2 merges para efetuar o balanceamento.")

    manifest = _merge_manifest(manga, chapter)
    outputs = manifest["outputs"]
    by_file = {
        str(item.get("file")): (idx, item)
        for idx, item in enumerate(outputs)
        if isinstance(item, dict) and item.get("file")
    }

    missing = [name for name in selected_names if name not in by_file]
    if missing:
        raise ValueError("Merge(s) não encontrado(s) no manifesto: " + ", ".join(missing))

    indexed = sorted((by_file[name][0], name, by_file[name][1]) for name in selected_names)
    indices = [item[0] for item in indexed]
    if indices != list(range(indices[0], indices[-1] + 1)):
        raise ValueError("Os merges selecionados precisam formar uma sequência contínua.")

    ordered_names = [item[1] for item in indexed]
    selected = [item[2] for item in indexed]

    try:
        region_start = int(selected[0]["global_start"])
        region_end = int(selected[-1]["global_end"])
    except Exception as exc:
        raise ValueError("Manifesto final sem limites globais válidos para a seleção.") from exc

    original_count = len(selected)
    total_height = region_end - region_start
    if total_height <= original_count:
        raise ValueError("Região selecionada pequena demais para redistribuição.")

    probe_target_height = total_height / float(original_count)
    probe_ideal_targets = [
        int(round(region_start + probe_target_height * ordinal))
        for ordinal in range(1, original_count)
    ]

    gray_image = _load_global_region(
        manga,
        chapter,
        region_start,
        region_end,
        mode="L",
    )
    gray = np.asarray(gray_image, dtype=np.uint8)

    global_safe, global_scan = _collect_global_safe_candidates(
        gray,
        region_start=region_start,
        region_end=region_end,
        ideal_targets=probe_ideal_targets,
    )

    visual_safe, balloon_scan = _filter_balloon_crossing_candidates(
        global_safe,
        manga=manga,
        chapter=chapter,
        region_start=region_start,
        region_end=region_end,
    )
    global_scan = {
        **global_scan,
        "visual_safety": balloon_scan,
        "safe_after_visual_filter": len(visual_safe),
    }
    global_safe = visual_safe

    candidate_counts = sorted(
        {
            c
            for c in (
                original_count - 1,
                original_count,
                original_count + 1,
                original_count + 2,
            )
            if c >= 2
        }
    )

    alternatives = []
    for candidate_count in candidate_counts:
        cuts, results, rank = _best_balanced_safe_composition(
            global_safe,
            region_start=region_start,
            region_end=region_end,
            count=candidate_count,
        )
        if cuts is None:
            continue
        normalized_spread = float(rank.get("spread") or 0) / max(
            1.0, float(rank.get("target_height") or 1.0)
        )
        complexity_penalty = abs(candidate_count - original_count) * 0.03
        selection_score = (
            float(rank.get("score") or 0.0)
            + normalized_spread * 0.25
            + complexity_penalty
        )
        alternatives.append(
            (
                selection_score,
                candidate_count,
                cuts,
                results,
                {
                    **rank,
                    "selection_score": round(selection_score, 8),
                    "original_count": original_count,
                    "candidate_count": candidate_count,
                    "complexity_penalty": round(complexity_penalty, 8),
                },
            )
        )

    if alternatives:
        alternatives.sort(key=lambda item: (item[0], item[1], item[2]))
        _, count, chosen_cuts, selected_results, balance_rank = alternatives[0]
    else:
        count = original_count
        chosen_cuts = None
        selected_results = []
        balance_rank = {
            "reason": "no_visually_safe_composition",
            "original_count": original_count,
            "candidate_counts": candidate_counts,
            "safe_candidates_after_visual_filter": len(global_safe),
            "visual_safety": balloon_scan,
        }

    target_height = total_height / float(count)
    ideal_targets = [
        int(round(region_start + target_height * ordinal))
        for ordinal in range(1, count)
    ]

    if chosen_cuts is None:
        proposal_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        generated_at = datetime.now().astimezone().isoformat(timespec="seconds")
        payload = {
            "schema": "balance_proposal_v2",
            "proposal_id": proposal_id,
            "chapter": chapter,
            "status": "SEM_PROPOSTA_SAFE",
            "generated_at": generated_at,
            "selected_files": ordered_names,
            "region": {
                "global_start": region_start,
                "global_end": region_end,
            },
            "target_height": round(target_height, 2),
            "cuts": [],
            "artifacts": [],
            "search": {
                "mode": "GLOBAL_SAFE_SWEEP",
                "scan": global_scan,
                "ranking": balance_rank,
            },
            "message": (
                "A varredura SAFE global encontrou "
                f"{global_scan.get('safe_candidates', 0)} corte(s) SAFE na região, "
                "mas não conseguiu formar uma composição completa "
                f"com {count} merges."
            ),
            "safety": {
                "merge_final_modified": False,
                "source_files_modified": False,
                "all_new_cuts_independently_safe": False,
            },
        }
        _persist_balance_proposal(manga, chapter, payload)
        return payload

    cut_details = []
    for ordinal, (selected_y, best) in enumerate(
        zip(chosen_cuts, selected_results),
        start=1,
    ):
        target_y = ideal_targets[ordinal - 1]
        cut_details.append(
            {
                "ordinal": ordinal,
                "target_y": target_y,
                "selected_y": int(selected_y),
                "distance": abs(int(selected_y) - target_y),
                "safe_candidates_found_global": len(global_safe),
                "search_mode": "GLOBAL_SAFE_SWEEP",
                "reason": best.reason,
                "edge_density": float(best.metrics.get("edge_density", 0.0)),
                "crossing_components": int(best.metrics.get("crossing_components", 0)),
            }
        )
    boundaries = [region_start, *chosen_cuts, region_end]
    heights = [
        boundaries[i + 1] - boundaries[i]
        for i in range(len(boundaries) - 1)
    ]
    if any(height <= 0 for height in heights):
        raise ValueError("A proposta gerou segmento de altura inválida.")

    proposal_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    proposal_dir = _proposal_root(manga) / chapter / proposal_id
    proposal_dir.mkdir(parents=True, exist_ok=True)

    rgb = _load_global_region(
        manga,
        chapter,
        region_start,
        region_end,
        mode="RGB",
    )
    artifacts = []
    for idx, (start, end) in enumerate(
        zip(boundaries[:-1], boundaries[1:]),
        start=1,
    ):
        local_start = start - region_start
        local_end = end - region_start
        name = f"proposal-{idx:03d}.png"
        rgb.crop((0, local_start, rgb.width, local_end)).save(
            proposal_dir / name,
            format="PNG",
        )
        artifacts.append(
            {
                "file": name,
                "global_start": start,
                "global_end": end,
                "height": end - start,
            }
        )

    generated_at = datetime.now().astimezone().isoformat(timespec="seconds")
    payload = {
        "schema": "balance_proposal_v2",
        "proposal_id": proposal_id,
        "chapter": chapter,
        "status": "PROPOSTA_GERADA",
        "generated_at": generated_at,
        "selected_files": ordered_names,
        "region": {
            "global_start": region_start,
            "global_end": region_end,
        },
        "original_heights": [
            int(item["global_end"]) - int(item["global_start"])
            for item in selected
        ],
        "target_height": round(target_height, 2),
        "cuts": cut_details,
        "artifacts": artifacts,
        "search": {
            "mode": "GLOBAL_SAFE_SWEEP",
            "scan": global_scan,
            "ranking": balance_rank,
        },
        "message": (
            "Proposta SAFE gerada por varredura global da região. "
            "Nenhum arquivo de 02_MERGE foi alterado."
        ),
        "safety": {
            "merge_final_modified": False,
            "source_files_modified": False,
            "all_new_cuts_independently_safe": True,
        },
    }
    _persist_balance_proposal(manga, chapter, payload)
    return payload


def balance_state(manga: Path) -> dict[str, Any]:
    root = _merge_root(manga)
    chapters = []
    if root.is_dir():
        chapter_dirs = sorted(
            (p for p in root.iterdir() if p.is_dir() and not p.name.startswith(".")),
            key=lambda p: _natural_key(p.name),
        )
        for chapter_dir in chapter_dirs:
            result = _chapter_analysis(chapter_dir)
            _write_manifest(manga, result)
            result["proposal"] = _latest_proposal(manga, chapter_dir.name)
            chapters.append(result)

    balanced = sum(1 for x in chapters if x["status"] == "BALANCEADO")
    unbalanced = sum(1 for x in chapters if x["status"] == "DESBALANCEADO")
    return {
        "ok": True,
        "rule": {
            "threshold_ratio": BALANCE_RATIO,
            "description": "Merge interno menor que 50% da média dos dois vizinhos.",
        },
        "summary": {
            "chapters": len(chapters),
            "balanced": balanced,
            "unbalanced": unbalanced,
        },
        "chapters": chapters,
    }
