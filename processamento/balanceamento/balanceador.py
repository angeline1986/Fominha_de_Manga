from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

import numpy as np
from PIL import Image

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
ProgressCallback = Callable[[int, int, str], None]


def _progress(cb: ProgressCallback | None, step: int, total: int, detail: str) -> None:
    if cb is not None:
        cb(int(step), int(total), str(detail))


def _natural_key(value: str) -> list[Any]:
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", value)]


def _secondary(manga: Path) -> Path:
    return manga / "FLUXO_SECUNDARIO"


def _merge_root(manga: Path) -> Path:
    return _secondary(manga) / "02_MERGE"


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

    pieces: list[Image.Image] = []
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


def _validate_selection(
    manga: Path,
    chapter: str,
    selected_files: list[str],
) -> tuple[list[str], list[dict[str, Any]], int, int]:
    names = [str(x) for x in selected_files if str(x).strip()]
    if len(names) < 2:
        raise ValueError("Selecione pelo menos 2 merges para efetuar o balanceamento.")

    manifest = _merge_manifest(manga, chapter)
    outputs = manifest["outputs"]
    by_file = {
        str(item.get("file")): (idx, item)
        for idx, item in enumerate(outputs)
        if isinstance(item, dict) and item.get("file")
    }

    missing = [name for name in names if name not in by_file]
    if missing:
        raise ValueError("Merge(s) não encontrado(s) no manifesto: " + ", ".join(missing))

    indexed = sorted((by_file[name][0], name, by_file[name][1]) for name in names)
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

    if region_end <= region_start:
        raise ValueError("Região global inválida para a seleção.")

    return ordered_names, selected, region_start, region_end


def _protected_balloon_ranges(
    manga: Path,
    chapter: str,
    region_start: int,
    region_end: int,
    *,
    margin_px: int = 16,
) -> tuple[list[tuple[int, int]], dict[str, Any]]:
    try:
        from processamento.limpeza_baloes.bubble_cleaner import resolve_model, detect_regions

        rgb_image = _load_global_region(manga, chapter, region_start, region_end, mode="RGB")
        rgb = np.asarray(rgb_image, dtype=np.uint8)
        model_path = resolve_model(None)
        detections = detect_regions(rgb, model_path, conf=0.55)
    except Exception as exc:
        raise RuntimeError(
            "Não foi possível executar a proteção visual de balões; "
            "o balanceamento foi interrompido sem gerar cortes."
        ) from exc

    protected: list[tuple[int, int]] = []
    for detection in detections:
        y1 = region_start + int(detection.y1) - int(margin_px)
        y2 = region_start + int(detection.y2) + int(margin_px)
        protected.append((max(region_start, y1), min(region_end, y2)))

    return protected, {
        "strategy": "manga_bubble_yolo_v1",
        "ok": True,
        "detections": len(detections),
        "protected_ranges": len(protected),
        "margin_px": int(margin_px),
    }


def _source_units_for_region(
    manga: Path,
    chapter: str,
    region_start: int,
    region_end: int,
) -> list[dict[str, Any]]:
    """Describe the source slices that intersect the selected global region.

    The balance heuristic deliberately reasons about source slices instead of
    Auto-Merge targets.  The first/last units may be partial when the selected
    MERGE region starts/ends inside a source image.
    """
    units: list[dict[str, Any]] = []
    cursor = 0
    for path in _source_files(manga, chapter):
        with Image.open(path) as im:
            item_start = cursor
            item_end = cursor + int(im.height)
            cursor = item_end
            overlap_start = max(int(region_start), item_start)
            overlap_end = min(int(region_end), item_end)
            if overlap_end <= overlap_start:
                if cursor >= region_end:
                    break
                continue

            top = overlap_start - item_start
            bottom = overlap_end - item_start
            gray = np.asarray(im.crop((0, top, im.width, bottom)).convert("L"), dtype=np.uint8)

        content = gray < 242
        row_density = content.mean(axis=1) if gray.size else np.zeros(1, dtype=float)
        units.append(
            {
                "file": path.name,
                "global_start": int(overlap_start),
                "global_end": int(overlap_end),
                "height": int(overlap_end - overlap_start),
                "features": np.array(
                    [
                        float(gray.mean()),
                        float(gray.std()),
                        float(content.mean()),
                        float(np.mean(gray >= 245)),
                        float(np.mean(gray <= 60)),
                        float(row_density.std()),
                    ],
                    dtype=np.float64,
                ),
            }
        )
        if cursor >= region_end:
            break

    if len(units) < 4:
        raise ValueError(
            "A região selecionada possui poucas slices-fonte para análise visual de partição."
        )
    return units


def _standardized_features(units: list[dict[str, Any]]) -> np.ndarray:
    matrix = np.stack([unit["features"] for unit in units])
    mean = matrix.mean(axis=0)
    std = matrix.std(axis=0)
    std[std == 0] = 1.0
    return (matrix - mean) / std


def _dispersion(z: np.ndarray, start: int, end: int) -> float:
    block = z[start:end]
    if len(block) <= 1:
        return 0.0
    center = block.mean(axis=0)
    return float(np.mean(np.linalg.norm(block - center, axis=1)))


def _centroid(z: np.ndarray, start: int, end: int) -> np.ndarray:
    return z[start:end].mean(axis=0)


def _discover_visual_anchors(
    units: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Discover visual partition anchors without Auto-Merge target geometry.

    Two independently evidenced mechanisms are used:
      1. a dominant abrupt regime rupture between consecutive source slices;
      2. a short, internally coherent visual island whose coherence degrades
         when either neighbour is absorbed.

    Geometry is used only to suppress pathological micro-fragmentation after
    anchors have been discovered; it does not create target positions.
    """
    z = _standardized_features(units)
    n = len(units)

    # Adjacent regime ruptures.  Keep only boundaries essentially tied with the
    # strongest rupture, avoiding a cascade of merely "large" local changes.
    strengths: list[dict[str, Any]] = []
    for idx in range(1, n):
        strength = float(np.linalg.norm(z[idx] - z[idx - 1]))
        strengths.append(
            {
                "index": idx,
                "y": int(units[idx]["global_start"]),
                "strength": strength,
                "left_file": units[idx - 1]["file"],
                "right_file": units[idx]["file"],
            }
        )

    max_strength = max(item["strength"] for item in strengths)
    strong_floor = max(2.0, max_strength * 0.90)
    strong = [item for item in strengths if item["strength"] >= strong_floor]
    strong.sort(key=lambda item: (-item["strength"], item["y"]))
    strong = strong[:3]

    strong_indices = {item["index"] for item in strong}

    # Search 3–4-slice visual islands.  Two-slice islands are intentionally not
    # promoted because they are too easy to overfit to local noise.
    islands: list[dict[str, Any]] = []
    for start in range(1, n - 2):
        for length in (3, 4):
            end = start + length
            if end >= n:
                continue

            # A visual island should not simply restate the dominant rupture.
            if start in strong_indices or end in strong_indices:
                continue

            internal = _dispersion(z, start, end)
            if internal <= 1e-9:
                internal = 1e-9

            left_expanded = _dispersion(z, start - 1, end)
            right_expanded = _dispersion(z, start, end + 1)
            gain_left = left_expanded / internal - 1.0
            gain_right = right_expanded / internal - 1.0

            left_context_start = max(0, start - 3)
            right_context_end = min(n, end + 3)
            center = _centroid(z, start, end)
            left_context = _centroid(z, left_context_start, start)
            right_context = _centroid(z, end, right_context_end)
            contrast = float(
                min(
                    np.linalg.norm(center - left_context),
                    np.linalg.norm(center - right_context),
                )
            )

            # Thresholds come directly from the diagnosed residual pattern:
            # internally compact, worsens on both expansions, and visually
            # distinct from both neighbourhoods.  They are Balanceamento-only.
            if not (
                internal <= 0.75
                and gain_left >= 0.25
                and gain_right >= 0.25
                and contrast >= 0.65
            ):
                continue

            score = (
                (gain_left + gain_right)
                + contrast
                - internal
            )
            islands.append(
                {
                    "start_index": start,
                    "end_index": end,
                    "start_y": int(units[start]["global_start"]),
                    "end_y": int(units[end]["global_start"]),
                    "files": [unit["file"] for unit in units[start:end]],
                    "internal_dispersion": round(float(internal), 6),
                    "gain_left": round(float(gain_left), 6),
                    "gain_right": round(float(gain_right), 6),
                    "contrast": round(float(contrast), 6),
                    "score": round(float(score), 6),
                }
            )

    islands.sort(
        key=lambda item: (
            -item["score"],
            item["internal_dispersion"],
            item["start_y"],
        )
    )

    # Keep non-overlapping islands, at most two per selected region.  This
    # preserves the "island" semantics instead of turning every low-dispersion
    # patch into a new chunk.
    accepted_islands: list[dict[str, Any]] = []
    occupied: list[tuple[int, int]] = []
    for island in islands:
        span = (island["start_index"], island["end_index"])
        if any(not (span[1] <= a or span[0] >= b) for a, b in occupied):
            continue
        accepted_islands.append(island)
        occupied.append(span)
        if len(accepted_islands) >= 2:
            break

    raw: list[dict[str, Any]] = []
    for item in strong:
        raw.append(
            {
                "y": int(item["y"]),
                "reason": "strong_regime_rupture",
                "priority": 100.0 + float(item["strength"]),
                "evidence": {
                    "strength": round(float(item["strength"]), 6),
                    "left_file": item["left_file"],
                    "right_file": item["right_file"],
                },
            }
        )

    for island in accepted_islands:
        priority = 80.0 + float(island["score"])
        evidence = {k: v for k, v in island.items() if k not in {"start_y", "end_y"}}
        raw.extend(
            [
                {
                    "y": int(island["start_y"]),
                    "reason": "visual_island_start",
                    "priority": priority,
                    "evidence": evidence,
                },
                {
                    "y": int(island["end_y"]),
                    "reason": "visual_island_end",
                    "priority": priority,
                    "evidence": evidence,
                },
            ]
        )

    # Deduplicate anchors and reject micro-fragmentation.  The minimum spacing
    # is derived from source-slice scale, not from selected MERGE count.
    median_height = float(np.median([unit["height"] for unit in units]))
    min_gap = max(1, int(round(median_height * 2.0)))
    region_start = int(units[0]["global_start"])
    region_end = int(units[-1]["global_end"])

    by_y: dict[int, dict[str, Any]] = {}
    for item in raw:
        current = by_y.get(item["y"])
        if current is None or item["priority"] > current["priority"]:
            by_y[item["y"]] = item

    chosen: list[dict[str, Any]] = []
    for item in sorted(by_y.values(), key=lambda x: (-x["priority"], x["y"])):
        y = int(item["y"])
        if y - region_start < min_gap or region_end - y < min_gap:
            continue
        if any(abs(y - int(other["y"])) < min_gap for other in chosen):
            continue
        chosen.append(item)

    chosen.sort(key=lambda item: item["y"])

    return chosen, {
        "mode": "VISUAL_PARTITION_V2",
        "unit_count": n,
        "median_source_height": round(median_height, 2),
        "minimum_anchor_gap": min_gap,
        "strong_ruptures": [
            {
                **item,
                "strength": round(float(item["strength"]), 6),
            }
            for item in strong
        ],
        "island_candidates": islands[:12],
        "accepted_islands": accepted_islands,
        "anchors": chosen,
    }


def _safe_candidates_near_anchor(
    gray: np.ndarray,
    *,
    anchor_y: int,
    left_limit: int,
    right_limit: int,
    region_start: int,
    region_end: int,
    protected_ranges: list[tuple[int, int]],
    candidate_limit: int = 64,
) -> tuple[list[Any], dict[str, Any]]:
    """Snap a visual anchor to a structurally SAFE cut.

    Level III is used only as a safety gate here; its local-search radius and
    target-selection strategy are intentionally not reused by Balanceamento.
    """
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

    # Corridor is derived from neighbouring visual anchors/region boundaries.
    left_room = max(1, int(anchor_y) - int(left_limit))
    right_room = max(1, int(right_limit) - int(anchor_y))
    radius = int(min(1800, max(240, 0.35 * min(left_room, right_room))))
    step = max(1, int(getattr(cfg, "local_search_step", 2)))
    lower = max(int(left_limit) + 1, int(anchor_y) - radius)
    upper = min(int(right_limit) - 1, int(anchor_y) + radius)

    candidates: list[Any] = []
    evaluated = 0
    balloon_rejected = 0

    # Evaluate nearest positions first so safety snapping cannot drift simply
    # because of scan direction.
    ys = list(range(lower, upper + 1, step))
    ys.sort(key=lambda y: (abs(y - int(anchor_y)), y))

    for y in ys:
        evaluated += 1
        if any(y1 <= y <= y2 for y1, y2 in protected_ranges):
            balloon_rejected += 1
            continue
        result = analyze_structural_candidate(
            gray,
            candidate_y=int(y),
            region=region,
            image_global_start=int(region_start),
            config=cfg,
        )
        if result.decision == Level3Decision.SAFE:
            candidates.append(result)
            if len(candidates) >= max(1, int(candidate_limit)):
                break

    candidates.sort(
        key=lambda item: (
            abs(int(item.candidate_y) - int(anchor_y)),
            float(item.metrics.get("edge_density", 1.0)),
            int(item.metrics.get("crossing_components", 999999)),
            int(item.candidate_y),
        )
    )

    return candidates, {
        "anchor_y": int(anchor_y),
        "lower": int(lower),
        "upper": int(upper),
        "radius": int(radius),
        "step": int(step),
        "evaluated": int(evaluated),
        "balloon_rejected": int(balloon_rejected),
        "safe_candidates": len(candidates),
        "candidate_limit": int(candidate_limit),
    }


def _snap_visual_anchors_to_safe_cuts(
    gray: np.ndarray,
    anchors: list[dict[str, Any]],
    *,
    region_start: int,
    region_end: int,
    protected_ranges: list[tuple[int, int]],
    source_boundaries: set[int],
) -> tuple[list[int] | None, list[Any], list[dict[str, Any]], dict[str, Any]]:
    if not anchors:
        return None, [], [], {"reason": "no_visual_partition_anchor"}

    ordered = sorted(anchors, key=lambda item: item["y"])
    selected_y: list[int] = []
    selected_results: list[Any] = []
    scans: list[dict[str, Any]] = []

    for idx, anchor in enumerate(ordered):
        left_anchor = region_start if idx == 0 else int(ordered[idx - 1]["y"])
        right_anchor = region_end if idx == len(ordered) - 1 else int(ordered[idx + 1]["y"])
        anchor_y = int(anchor["y"])

        # A boundary between two immutable source images is already a real
        # separation in IMG. Materializing it does not cut any source pixel, so
        # it must not be rejected merely because Level III cannot find an
        # internal structural band around the same coordinate.
        if anchor_y in source_boundaries:
            result = SimpleNamespace(
                candidate_y=anchor_y,
                reason="source_boundary_safe",
                metrics={
                    "edge_density": 0.0,
                    "crossing_components": 0,
                },
            )
            scans.append({
                "anchor_y": anchor_y,
                "mode": "SOURCE_BOUNDARY",
                "evaluated": 0,
                "balloon_rejected": 0,
                "safe_candidates": 1,
                "selected_y": anchor_y,
                "reason": "source_boundary_safe",
            })
        else:
            candidates, scan = _safe_candidates_near_anchor(
                gray,
                anchor_y=anchor_y,
                left_limit=left_anchor,
                right_limit=right_anchor,
                region_start=region_start,
                region_end=region_end,
                protected_ranges=protected_ranges,
            )
            scans.append(scan)
            if not candidates:
                return None, [], scans, {
                    "reason": "visual_anchor_without_safe_candidate",
                    "anchor_y": anchor_y,
                    "anchor_reason": anchor["reason"],
                }
            result = candidates[0]

        y = int(result.candidate_y)
        if selected_y and y <= selected_y[-1]:
            return None, [], scans, {
                "reason": "safe_snap_not_ordered",
                "anchor_y": int(anchor["y"]),
                "selected_y": y,
            }
        selected_y.append(y)
        selected_results.append(result)

    boundaries = [region_start, *selected_y, region_end]
    heights = [b - a for a, b in zip(boundaries, boundaries[1:])]
    if any(height <= 0 for height in heights):
        return None, [], scans, {"reason": "invalid_safe_partition_heights"}

    return selected_y, selected_results, scans, {
        "reason": "visual_partition_safe_snap_v2",
        "heights": heights,
        "block_count": len(heights),
        "anchor_count": len(ordered),
        "source_boundary_count": sum(
            1 for y in selected_y if int(y) in source_boundaries
        ),
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


def _persist_no_proposal(
    manga: Path,
    chapter: str,
    *,
    ordered_names: list[str],
    region_start: int,
    region_end: int,
    original_heights: list[int],
    visual_safety: dict[str, Any],
    partition_analysis: dict[str, Any],
    scans: list[dict[str, Any]],
    ranking: dict[str, Any],
) -> dict[str, Any]:
    proposal_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    generated_at = datetime.now().astimezone().isoformat(timespec="seconds")
    payload = {
        "schema": "balance_proposal_visual_partition_v2",
        "proposal_id": proposal_id,
        "chapter": chapter,
        "status": "SEM_PROPOSTA_SAFE",
        "generated_at": generated_at,
        "selected_files": ordered_names,
        "region": {"global_start": region_start, "global_end": region_end},
        "original_heights": original_heights,
        "cuts": [],
        "artifacts": [],
        "search": {
            "mode": "VISUAL_PARTITION_V2",
            "partition_analysis": partition_analysis,
            "safe_snap_scans": scans,
            "visual_safety": visual_safety,
            "ranking": ranking,
        },
        "message": (
            "A análise visual não encontrou uma partição completa que também pudesse "
            "ser materializada somente com cortes estruturalmente SAFE. "
            "Nenhum arquivo de 02_MERGE foi alterado."
        ),
        "safety": {
            "merge_final_modified": False,
            "source_files_modified": False,
            "all_new_cuts_independently_safe": False,
        },
    }
    _persist_balance_proposal(manga, chapter, payload)
    return payload



def prepare_manual_balance(
    manga: Path,
    chapter: str,
    selected_files: list[str],
    *,
    progress_callback: ProgressCallback | None = None,
) -> dict[str, Any]:
    # Prepara editor manual; não altera IMG nem MERGE final.
    chapter = str(chapter)
    _progress(progress_callback, 1, 3, "validando seleção e manifesto...")
    ordered_names, selected, region_start, region_end = _validate_selection(manga, chapter, selected_files)

    current_cuts = [
        int(item["global_end"]) for item in selected[:-1]
        if region_start < int(item["global_end"]) < region_end
    ]
    if not current_cuts:
        raise ValueError("A seleção não possui fronteiras internas para edição.")

    _progress(progress_callback, 2, 3, "reconstruindo slices originais...")
    units = _source_units_for_region(manga, chapter, region_start, region_end)
    source_slices = []
    for unit in units:
        start = max(region_start, int(unit["global_start"]))
        end = min(region_end, int(unit["global_end"]))
        if end > start:
            source_slices.append({
                "file": str(unit["file"]), "global_start": start,
                "global_end": end, "height": end - start,
            })

    proposal_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    proposal_dir = _proposal_root(manga) / chapter / proposal_id
    proposal_dir.mkdir(parents=True, exist_ok=True)
    rgb = _load_global_region(manga, chapter, region_start, region_end, mode="RGB")
    preview_name = "manual-source.png"
    rgb.save(proposal_dir / preview_name, format="PNG")

    generated_at = datetime.now().astimezone().isoformat(timespec="seconds")
    payload = {
        "schema": "balance_manual_editor_v1",
        "proposal_id": proposal_id, "chapter": chapter, "status": "AJUSTE_MANUAL",
        "generated_at": generated_at, "selected_files": ordered_names,
        "region": {"global_start": region_start, "global_end": region_end},
        "source_slices": source_slices, "source_preview": preview_name,
        "cuts": [{"ordinal": i, "selected_y": y, "origin": "current_merge_boundary"}
                 for i, y in enumerate(current_cuts, start=1)],
        "artifacts": [],
        "message": "Ajuste os cortes livremente e execute para gerar a proposta.",
        "safety": {"merge_final_modified": False, "source_files_modified": False,
                   "manual_cut_confirmation_required": True},
    }
    _persist_balance_proposal(manga, chapter, payload)
    _progress(progress_callback, 3, 3, "editor manual preparado.")
    return payload


def generate_manual_balance(
    manga: Path,
    chapter: str,
    selected_files: list[str],
    cuts: list[int],
    *,
    progress_callback: ProgressCallback | None = None,
) -> dict[str, Any]:
    # Materializa exatamente os Y enviados; sem snap e sem alterar 02_MERGE.
    chapter = str(chapter)
    _progress(progress_callback, 1, 4, "validando seleção e cortes manuais...")
    ordered_names, selected, region_start, region_end = _validate_selection(manga, chapter, selected_files)
    try:
        chosen = [int(y) for y in cuts]
    except Exception as exc:
        raise ValueError("Cortes manuais inválidos.") from exc
    if not chosen:
        raise ValueError("Defina pelo menos um corte.")
    if chosen != sorted(set(chosen)):
        raise ValueError("Os cortes precisam ser únicos e estar em ordem crescente.")
    if any(y <= region_start or y >= region_end for y in chosen):
        raise ValueError("Todos os cortes precisam estar dentro da região selecionada.")

    _progress(progress_callback, 2, 4, "reconstruindo região a partir de IMG...")
    rgb = _load_global_region(manga, chapter, region_start, region_end, mode="RGB")
    units = _source_units_for_region(manga, chapter, region_start, region_end)
    source_slices = []
    for unit in units:
        start = max(region_start, int(unit["global_start"]))
        end = min(region_end, int(unit["global_end"]))
        if end > start:
            source_slices.append({
                "file": str(unit["file"]), "global_start": start,
                "global_end": end, "height": end - start,
            })

    proposal_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    proposal_dir = _proposal_root(manga) / chapter / proposal_id
    proposal_dir.mkdir(parents=True, exist_ok=True)
    preview_name = "manual-source.png"
    rgb.save(proposal_dir / preview_name, format="PNG")

    _progress(progress_callback, 3, 4, "gerando blocos nos cortes definidos...")
    boundaries = [region_start, *chosen, region_end]
    artifacts = []
    for idx, (start, end) in enumerate(zip(boundaries[:-1], boundaries[1:]), start=1):
        name = f"proposal-{idx:03d}.png"
        rgb.crop((0, start-region_start, rgb.width, end-region_start)).save(proposal_dir / name, format="PNG")
        artifacts.append({"file": name, "global_start": int(start),
                          "global_end": int(end), "height": int(end-start)})

    generated_at = datetime.now().astimezone().isoformat(timespec="seconds")
    payload = {
        "schema": "balance_manual_result_v1",
        "proposal_id": proposal_id, "chapter": chapter, "status": "PROPOSTA_GERADA",
        "generated_at": generated_at, "selected_files": ordered_names,
        "region": {"global_start": region_start, "global_end": region_end},
        "source_slices": source_slices, "source_preview": preview_name,
        "output_count": len(artifacts),
        "cuts": [{"ordinal": i, "selected_y": y, "origin": "user_defined"}
                 for i, y in enumerate(chosen, start=1)],
        "artifacts": artifacts,
        "message": "Proposta gerada exatamente nos cortes definidos pelo usuário. O MERGE final não foi alterado.",
        "safety": {"merge_final_modified": False, "source_files_modified": False,
                   "cuts_user_defined": True},
    }
    _persist_balance_proposal(manga, chapter, payload)
    _progress(progress_callback, 4, 4, "proposta manual gerada.")
    return payload


def generate_balance_proposal(
    manga: Path,
    chapter: str,
    selected_files: list[str],
    *,
    progress_callback: ProgressCallback | None = None,
) -> dict[str, Any]:
    chapter = str(chapter)
    total_steps = 6

    _progress(progress_callback, 1, total_steps, "validando seleção e manifesto...")
    ordered_names, selected, region_start, region_end = _validate_selection(
        manga, chapter, selected_files
    )
    original_heights = [
        int(item["global_end"]) - int(item["global_start"])
        for item in selected
    ]

    _progress(progress_callback, 2, total_steps, "reconstruindo região a partir de IMG...")
    gray_image = _load_global_region(manga, chapter, region_start, region_end, mode="L")
    gray = np.asarray(gray_image, dtype=np.uint8)

    _progress(progress_callback, 3, total_steps, "extraindo regimes visuais das slices-fonte...")
    units = _source_units_for_region(manga, chapter, region_start, region_end)
    anchors, partition_analysis = _discover_visual_anchors(units)

    if not anchors:
        return _persist_no_proposal(
            manga,
            chapter,
            ordered_names=ordered_names,
            region_start=region_start,
            region_end=region_end,
            original_heights=original_heights,
            visual_safety={"strategy": "not_executed_no_visual_anchor", "ok": False},
            partition_analysis=partition_analysis,
            scans=[],
            ranking={"reason": "no_visual_partition_anchor"},
        )

    _progress(progress_callback, 4, total_steps, "detectando regiões protegidas...")
    protected_ranges, visual_safety = _protected_balloon_ranges(
        manga, chapter, region_start, region_end
    )

    _progress(progress_callback, 5, total_steps, "validando cortes da partição visual...")
    source_boundaries = {
        int(unit["global_end"])
        for unit in units[:-1]
        if region_start < int(unit["global_end"]) < region_end
    }
    chosen_cuts, selected_results, scans, ranking = _snap_visual_anchors_to_safe_cuts(
        gray,
        anchors,
        region_start=region_start,
        region_end=region_end,
        protected_ranges=protected_ranges,
        source_boundaries=source_boundaries,
    )
    if chosen_cuts is None:
        return _persist_no_proposal(
            manga,
            chapter,
            ordered_names=ordered_names,
            region_start=region_start,
            region_end=region_end,
            original_heights=original_heights,
            visual_safety=visual_safety,
            partition_analysis=partition_analysis,
            scans=scans,
            ranking=ranking,
        )

    _progress(progress_callback, 6, total_steps, "gravando proposta de partição visual...")
    boundaries = [region_start, *chosen_cuts, region_end]
    rgb = _load_global_region(manga, chapter, region_start, region_end, mode="RGB")

    proposal_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    proposal_dir = _proposal_root(manga) / chapter / proposal_id
    proposal_dir.mkdir(parents=True, exist_ok=True)

    artifacts: list[dict[str, Any]] = []
    for idx, (start, end) in enumerate(zip(boundaries[:-1], boundaries[1:]), start=1):
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
                "global_start": int(start),
                "global_end": int(end),
                "height": int(end - start),
            }
        )

    cut_details: list[dict[str, Any]] = []
    ordered_anchors = sorted(anchors, key=lambda item: item["y"])
    for ordinal, (anchor, selected_y, result) in enumerate(
        zip(ordered_anchors, chosen_cuts, selected_results),
        start=1,
    ):
        cut_details.append(
            {
                "ordinal": ordinal,
                "anchor_y": int(anchor["y"]),
                "selected_y": int(selected_y),
                "snap_distance": abs(int(selected_y) - int(anchor["y"])),
                "anchor_reason": anchor["reason"],
                "anchor_evidence": anchor["evidence"],
                "safety_reason": result.reason,
                "edge_density": float(result.metrics.get("edge_density", 0.0)),
                "crossing_components": int(result.metrics.get("crossing_components", 0)),
            }
        )

    generated_at = datetime.now().astimezone().isoformat(timespec="seconds")
    payload = {
        "schema": "balance_proposal_visual_partition_v2",
        "proposal_id": proposal_id,
        "chapter": chapter,
        "status": "PROPOSTA_GERADA",
        "generated_at": generated_at,
        "selected_files": ordered_names,
        "region": {"global_start": region_start, "global_end": region_end},
        "original_heights": original_heights,
        "output_count": len(artifacts),
        "cuts": cut_details,
        "artifacts": artifacts,
        "search": {
            "mode": "VISUAL_PARTITION_V2",
            "partition_analysis": partition_analysis,
            "safe_snap_scans": scans,
            "visual_safety": visual_safety,
            "ranking": ranking,
        },
        "message": (
            "Proposta gerada pela heurística visual de Balanceamento v2. "
            "A quantidade de blocos foi inferida da partição visual e não do número "
            "de merges selecionados. Nenhum arquivo de 02_MERGE foi alterado."
        ),
        "safety": {
            "merge_final_modified": False,
            "source_files_modified": False,
            "all_new_cuts_independently_safe": True,
        },
    }
    _persist_balance_proposal(manga, chapter, payload)
    return payload
