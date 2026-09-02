from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np
from PIL import Image

from processamento.unificacao_imagens import image_stitcher as v3


@dataclass(frozen=True)
class Level2Config:
    target_height: int = v3.DEFAULT_TARGET_HEIGHT
    min_chunk_height: int = v3.DEFAULT_MIN_CHUNK_HEIGHT
    max_chunk_height: int = v3.DEFAULT_MAX_CHUNK_HEIGHT
    min_white_band: int = v3.DEFAULT_MIN_WHITE_BAND
    min_uniform_band: int = v3.DEFAULT_MIN_WHITE_BAND
    uniform_max_channel_std: float = 4.0
    uniform_max_row_delta: float = 3.0
    preferred_source_files: int = 4


@dataclass(frozen=True)
class UniformColorBand:
    start: int
    end: int
    height: int
    mean_rgb: tuple[int, int, int]
    max_channel_std_mean: float
    max_channel_std_max: float
    row_delta_mean: float
    candidate_type: str = "uniform_color_band"

    @property
    def color_hex(self) -> str:
        r, g, b = self.mean_rgb
        return f"#{r:02x}{g:02x}{b:02x}"


def _candidate_payload(band) -> dict:
    center = (int(band.start) + int(band.end)) // 2
    candidate_type = str(getattr(band, "candidate_type", "white_band"))
    item = {
        "center": center,
        "band_start": int(band.start),
        "band_end": int(band.end),
        "band_height": int(band.height),
        "candidate_type": candidate_type,
    }
    if candidate_type == "uniform_color_band":
        item.update({
            "color_hex": str(getattr(band, "color_hex", "")),
            "mean_rgb": [int(x) for x in getattr(band, "mean_rgb", (0, 0, 0))],
            "max_channel_std_mean": round(float(getattr(band, "max_channel_std_mean", 0.0)), 4),
            "max_channel_std_max": round(float(getattr(band, "max_channel_std_max", 0.0)), 4),
            "row_delta_mean": round(float(getattr(band, "row_delta_mean", 0.0)), 4),
        })
    else:
        item["band_white_ratio_mean"] = round(float(band.white_ratio_mean), 5)
    return item


def _eligible_candidates(start: int, end: int, bands: Iterable, config: Level2Config) -> tuple[list[dict], list[dict]]:
    eligible: list[dict] = []
    rejected: list[dict] = []
    for band in bands:
        item = _candidate_payload(band)
        center = item["center"]
        if center <= start or center >= end:
            continue
        minimum = int(config.min_uniform_band if item["candidate_type"] == "uniform_color_band" else config.min_white_band)
        if item["band_height"] < minimum:
            item["decision"] = "rejected"
            item["reason"] = (
                "uniform_band_too_short"
                if item["candidate_type"] == "uniform_color_band"
                else "white_band_too_short"
            )
            rejected.append(item)
            continue
        item["decision"] = "eligible"
        eligible.append(item)

    # Candidatos muito próximos representam a mesma faixa visual. Mantemos o
    # mais largo; em empate, preservamos a faixa branca V3 já comprovada.
    eligible.sort(key=lambda x: (x["center"], -x["band_height"]))
    deduped: list[dict] = []
    for item in eligible:
        if deduped and abs(item["center"] - deduped[-1]["center"]) <= 8:
            current = deduped[-1]
            rank_item = (item["band_height"], item["candidate_type"] == "white_band")
            rank_current = (current["band_height"], current["candidate_type"] == "white_band")
            if rank_item > rank_current:
                deduped[-1] = item
        else:
            deduped.append(item)
    rejected.sort(key=lambda x: x["center"])
    return deduped, rejected


def _row_uniformity(image: Image.Image, *, sample_width: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rgb = image.convert("RGB")
    width, height = rgb.size
    if width > sample_width:
        rgb = rgb.resize((sample_width, height), Image.Resampling.BILINEAR)
    arr = np.asarray(rgb, dtype=np.float32)
    means = arr.mean(axis=1)
    channel_std = arr.std(axis=1)
    max_std = channel_std.max(axis=1)
    deltas = np.zeros(height, dtype=np.float32)
    if height > 1:
        deltas[1:] = np.abs(means[1:] - means[:-1]).max(axis=1)
    return means, max_std, deltas


def analyze_uniform_color_bands(
    pages: Sequence[Path],
    *,
    sample_width: int = v3.DEFAULT_SAMPLE_WIDTH,
    max_channel_std: float = 4.0,
    max_row_delta: float = 3.0,
) -> list[UniformColorBand]:
    """Detecta faixas largas e visualmente uniformes, sem exigir cor branca.

    É uma heurística conservadora de Nível II: cada linha precisa ter baixa
    variação transversal e pouca mudança de cor em relação à linha anterior.
    Assim, gutters bege/cinza/preto/colorido podem ser candidatos, mas texto,
    personagens e detalhes atravessando a faixa elevam o desvio e a removem.
    """
    all_means: list[np.ndarray] = []
    all_std: list[np.ndarray] = []
    all_delta: list[np.ndarray] = []
    for path in pages:
        with Image.open(path) as image:
            image.load()
            means, stds, deltas = _row_uniformity(image, sample_width=sample_width)
        all_means.append(means)
        all_std.append(stds)
        all_delta.append(deltas)
    if not all_means:
        return []

    means = np.concatenate(all_means, axis=0)
    stds = np.concatenate(all_std, axis=0)
    deltas = np.concatenate(all_delta, axis=0)
    is_uniform = (stds <= float(max_channel_std)) & (deltas <= float(max_row_delta))

    bands: list[UniformColorBand] = []
    start: int | None = None
    for idx, value in enumerate(is_uniform):
        if value and start is None:
            start = idx
        elif not value and start is not None:
            if idx > start:
                sl = slice(start, idx)
                mean_rgb = tuple(int(round(x)) for x in means[sl].mean(axis=0))
                bands.append(UniformColorBand(
                    start=start,
                    end=idx,
                    height=idx - start,
                    mean_rgb=mean_rgb,
                    max_channel_std_mean=float(stds[sl].mean()),
                    max_channel_std_max=float(stds[sl].max()),
                    row_delta_mean=float(deltas[sl].mean()),
                ))
            start = None
    if start is not None and len(is_uniform) > start:
        sl = slice(start, len(is_uniform))
        mean_rgb = tuple(int(round(x)) for x in means[sl].mean(axis=0))
        bands.append(UniformColorBand(
            start=start,
            end=len(is_uniform),
            height=len(is_uniform) - start,
            mean_rgb=mean_rgb,
            max_channel_std_mean=float(stds[sl].mean()),
            max_channel_std_max=float(stds[sl].max()),
            row_delta_mean=float(deltas[sl].mean()),
        ))
    return bands


def _source_count(a: int, b: int, source_intervals: Sequence[tuple[int, int]] | None) -> int:
    if not source_intervals:
        return 0
    return sum(1 for s, e in source_intervals if int(e) > int(a) and int(s) < int(b))


def _path_quality(path: list[int], cfg: Level2Config, source_intervals: Sequence[tuple[int, int]] | None) -> tuple[int, int, int, int]:
    heights = [b - a for a, b in zip(path, path[1:])]
    source_counts = [_source_count(a, b, source_intervals) for a, b in zip(path, path[1:])]
    source_shortfall = sum(max(0, int(cfg.preferred_source_files) - count) for count in source_counts) if source_intervals else 0
    deviation = sum(abs(h - int(cfg.target_height)) for h in heights)
    imbalance = max(heights) - min(heights) if heights else 0
    return source_shortfall, deviation, imbalance, len(heights)


def solve_pending_region(
    start: int,
    end: int,
    bands: Iterable,
    config: Level2Config | None = None,
    *,
    source_intervals: Sequence[tuple[int, int]] | None = None,
) -> dict:
    """Encontra a melhor composição segura dentro de um residual do Nível I.

    Candidatos podem ser faixas brancas V3 ou faixas de cor uniforme detectadas
    pelo próprio Nível II. A cor não autoriza o corte: somente a uniformidade
    comprovada torna a faixa elegível. Entre caminhos SAFE, o Nível II prefere
    composições equilibradas e, como preferência editorial leve, chunks que
    agreguem ao menos quatro arquivos-fonte. Edge chunk < 3.000 px permanece
    último fallback e só pode ocorrer na borda real do residual.
    """
    cfg = config or Level2Config()
    start = int(start)
    end = int(end)
    if end <= start:
        raise ValueError("Intervalo Level II inválido.")

    height = end - start
    if height <= int(cfg.max_chunk_height):
        return {
            "status": "resolved",
            "resolved_intervals": [[start, end]],
            "residual_interval": None,
            "selected_cuts": [],
            "eligible_candidates": [],
            "rejected_candidates": [],
            "strategy": "already_within_max_height",
            "balance": _balance_payload([start, end], cfg, source_intervals),
        }

    eligible, rejected = _eligible_candidates(start, end, bands, cfg)
    nodes = [start] + [x["center"] for x in eligible] + [end]
    candidate_by_center = {x["center"]: x for x in eligible}

    def build_path(*, allow_small_edges: bool):
        # best[y] = (edge_exceptions, source_shortfall, deviation, imbalance,
        #            chunks, negative_candidate_quality, path)
        best: dict[int, tuple[int, int, int, int, int, float, list[int]]] = {
            start: (0, 0, 0, 0, 0, 0.0, [start])
        }
        for node in nodes[1:]:
            is_end = node == end
            choices = []
            for prev, state in list(best.items()):
                delta = node - prev
                if delta > int(cfg.max_chunk_height):
                    continue
                small = delta < int(cfg.min_chunk_height)
                edge_chunk = prev == start or is_end
                if small and not (allow_small_edges and edge_chunk):
                    continue
                path = state[-1] + [node]
                source_shortfall, deviation, imbalance, chunks = _path_quality(path, cfg, source_intervals)
                edge_exceptions = state[0] + (1 if small else 0)
                quality = state[5]
                if not is_end:
                    cand = candidate_by_center[node]
                    if cand["candidate_type"] == "white_band":
                        candidate_quality = float(cand["band_height"]) + float(cand.get("band_white_ratio_mean", 0.0))
                    else:
                        # Quanto mais larga e menor o desvio, maior a qualidade.
                        candidate_quality = float(cand["band_height"]) - float(cand.get("max_channel_std_mean", 0.0))
                    quality -= candidate_quality
                choices.append((edge_exceptions, source_shortfall, deviation, imbalance, chunks, quality, path))
            if choices:
                best[node] = min(choices, key=lambda x: (x[0], x[1], x[2], x[3], x[4], x[5], x[6]))
        return best

    strict_best = build_path(allow_small_edges=False)
    if end in strict_best:
        path = strict_best[end][-1]
        cuts = path[1:-1]
        return {
            "status": "resolved",
            "resolved_intervals": [[a, b] for a, b in zip(path, path[1:])],
            "residual_interval": None,
            "selected_cuts": [dict(candidate_by_center[x], path_status="selected", selection_reason="best_safe_balanced_path") for x in cuts],
            "eligible_candidates": eligible,
            "rejected_candidates": rejected,
            "strategy": "bounded_safe_balanced_path",
            "path_mode": "preferred_minimum",
            "edge_chunk_relaxation_used": False,
            "edge_chunks": [],
            "balance": _balance_payload(path, cfg, source_intervals),
        }

    edge_best = build_path(allow_small_edges=True)
    if end in edge_best:
        path = edge_best[end][-1]
        cuts = path[1:-1]
        intervals = [[a, b] for a, b in zip(path, path[1:])]
        edge_chunks = []
        for idx, (a, b) in enumerate(zip(path, path[1:])):
            if b - a >= int(cfg.min_chunk_height):
                continue
            position = "start" if idx == 0 else ("end" if idx == len(path) - 2 else "internal")
            if position == "internal":
                raise AssertionError("Level II criou edge chunk pequeno no interior do residual.")
            edge_chunks.append({
                "position": position,
                "global_start": int(a),
                "global_end": int(b),
                "height": int(b - a),
                "preferred_min_chunk_height": int(cfg.min_chunk_height),
                "reason": "safe_residual_edge_below_preferred_minimum",
            })
        return {
            "status": "resolved",
            "resolved_intervals": intervals,
            "residual_interval": None,
            "selected_cuts": [dict(candidate_by_center[x], path_status="selected", selection_reason="safe_edge_chunk_last_fallback") for x in cuts],
            "eligible_candidates": eligible,
            "rejected_candidates": rejected,
            "strategy": "bounded_safe_balanced_path_with_edge_chunk",
            "path_mode": "safe_edge_chunk_last_fallback",
            "edge_chunk_relaxation_used": bool(edge_chunks),
            "edge_chunks": edge_chunks,
            "balance": _balance_payload(path, cfg, source_intervals),
        }

    reachable = [x for x in candidate_by_center if x in strict_best and end - x >= int(cfg.min_chunk_height)]
    if not reachable:
        diagnostics = []
        for item in eligible:
            cand = dict(item)
            cand["visual_status"] = "safe"
            first_height = int(cand["center"]) - start
            last_height = end - int(cand["center"])
            if first_height < int(cfg.min_chunk_height) or last_height < int(cfg.min_chunk_height):
                cand["path_status"] = "edge_candidate"
                cand["path_reason"] = "edge_chunk_below_preferred_minimum"
            else:
                cand["path_status"] = "not_reachable"
                cand["path_reason"] = "no_complete_safe_path"
            diagnostics.append(cand)
        return {
            "status": "unresolved",
            "resolved_intervals": [],
            "residual_interval": [start, end],
            "selected_cuts": [],
            "eligible_candidates": diagnostics,
            "rejected_candidates": rejected,
            "strategy": "no_reachable_safe_path",
            "path_mode": "no_complete_path",
            "edge_chunk_relaxation_used": False,
            "edge_chunks": [],
        }

    # Para avanço parcial, escolhemos o prefixo cuja composição é melhor, e não
    # simplesmente o candidato geometricamente mais distante.
    scored = []
    for last in reachable:
        path = strict_best[last][-1]
        source_shortfall, deviation, imbalance, chunks = _path_quality(path, cfg, source_intervals)
        scored.append((source_shortfall, deviation, imbalance, -last, chunks, last, path))
    _, _, _, _, _, last, path = min(scored)
    cuts = path[1:]
    return {
        "status": "partial",
        "resolved_intervals": [[a, b] for a, b in zip(path, path[1:])],
        "residual_interval": [last, end],
        "selected_cuts": [dict(candidate_by_center[x], path_status="selected", selection_reason="best_safe_balanced_prefix") for x in cuts],
        "eligible_candidates": eligible,
        "rejected_candidates": rejected,
        "strategy": "bounded_safe_balanced_prefix",
        "path_mode": "preferred_minimum_partial",
        "edge_chunk_relaxation_used": False,
        "edge_chunks": [],
        "balance": _balance_payload(path, cfg, source_intervals),
    }


def _balance_payload(path: list[int], cfg: Level2Config, source_intervals: Sequence[tuple[int, int]] | None) -> dict:
    chunks = []
    for a, b in zip(path, path[1:]):
        chunks.append({
            "global_start": int(a),
            "global_end": int(b),
            "height": int(b - a),
            "source_file_count": int(_source_count(a, b, source_intervals)),
            "preferred_source_files_met": (
                _source_count(a, b, source_intervals) >= int(cfg.preferred_source_files)
                if source_intervals else None
            ),
        })
    return {
        "preferred_source_files": int(cfg.preferred_source_files),
        "preference_is_not_safety_rule": True,
        "chunks": chunks,
    }
