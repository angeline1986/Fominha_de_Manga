#!/usr/bin/env python3
"""Texto Off — Nível II: detector V3 + LaMa localizado sobre máscaras do Cleaner V2.

Este módulo é executado no ambiente isolado do Cleaner V2. Ele não repete OCR nem
recria máscaras: analisa o resultado do Nível I, seleciona apenas componentes
suspeitos e substitui somente esses pixels por reconstrução LaMa baseada na
imagem original.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import tempfile

import cv2
import numpy as np
import torch
from PIL import Image
from simple_lama_inpainting import SimpleLama

MIN_AREA = 20_000
MIN_RECTANGULARITY = 0.85
TYPE_A_MIN_STD = 2.5
TYPE_B_MAX_STD = 1.5
TYPE_B_MIN_CONTEXT_RANGE = 25.0
TYPE_B_MAX_INTERNAL_MEAN = 245.0
BAND = 12
PADDING = 160

SUPPORTED_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp', '.bmp'}


def _single_artifact(folder: Path, stem: str, kind: str) -> Path:
    matches = sorted(p for p in folder.glob(f"{stem}_{kind}.*") if p.is_file())
    if len(matches) != 1:
        raise RuntimeError(
            f"Esperado exatamente um artefato {kind} para {stem}; encontrados: "
            + (", ".join(p.name for p in matches) if matches else "nenhum")
        )
    return matches[0]


def _load_mask(path: Path) -> np.ndarray:
    raw = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if raw is None:
        raise RuntimeError(f"Não foi possível abrir máscara: {path}")
    if raw.ndim == 2:
        gray = raw
    else:
        gray = np.max(raw[:, :, :3], axis=2)
    return (gray > 8).astype(np.uint8)


def _component_metrics(clean_rgb: np.ndarray, component: np.ndarray,
                       x: int, y: int, w: int, h: int) -> dict | None:
    gray = cv2.cvtColor(clean_rgb, cv2.COLOR_RGB2GRAY)
    inside = gray[component > 0]
    if inside.size == 0:
        return None

    internal_mean = float(inside.mean())
    internal_std = float(inside.std())
    height, width = gray.shape
    sides: list[float] = []

    if y > 0:
        band = gray[max(0, y-BAND):y, x:x+w]
        if band.size:
            sides.append(float(band.mean()))
    if y + h < height:
        band = gray[y+h:min(height, y+h+BAND), x:x+w]
        if band.size:
            sides.append(float(band.mean()))
    if x > 0:
        band = gray[y:y+h, max(0, x-BAND):x]
        if band.size:
            sides.append(float(band.mean()))
    if x + w < width:
        band = gray[y:y+h, x+w:min(width, x+w+BAND)]
        if band.size:
            sides.append(float(band.mean()))

    context_range = max(sides) - min(sides) if len(sides) >= 2 else 0.0
    return {
        'internal_mean': internal_mean,
        'internal_std': internal_std,
        'context_range': context_range,
        'side_values': sides,
    }


def _classify(metrics: dict) -> str | None:
    if metrics['internal_std'] >= TYPE_A_MIN_STD:
        return 'TYPE_A'
    if (
        metrics['internal_std'] <= TYPE_B_MAX_STD
        and metrics['context_range'] >= TYPE_B_MIN_CONTEXT_RANGE
        and metrics['internal_mean'] <= TYPE_B_MAX_INTERNAL_MEAN
        and len(metrics['side_values']) >= 3
    ):
        return 'TYPE_B'
    return None


def _find_model() -> Path:
    env = os.environ.get('LAMA_MODEL')
    if env:
        candidate = Path(env).expanduser()
        if candidate.is_file():
            return candidate.resolve()

    home = Path.home()
    candidates = [
        home / 'Library/Caches/pcleaner/model/anime-manga-big-lama.pt',
        home / '.cache/pcleaner/model/anime-manga-big-lama.pt',
    ]
    xdg = os.environ.get('XDG_CACHE_HOME')
    if xdg:
        candidates.append(Path(xdg).expanduser() / 'pcleaner/model/anime-manga-big-lama.pt')

    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise FileNotFoundError(
        'Modelo anime-manga-big-lama.pt não encontrado no cache do pcleaner. '
        'Execute antes um teste de inpainting do Cleaner V2 para baixar o modelo.'
    )


def _detect_suspects(clean_rgb: np.ndarray, mask_bin: np.ndarray) -> list[dict]:
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask_bin, connectivity=8)
    suspects: list[dict] = []
    for idx in range(1, count):
        x = int(stats[idx, cv2.CC_STAT_LEFT])
        y = int(stats[idx, cv2.CC_STAT_TOP])
        w = int(stats[idx, cv2.CC_STAT_WIDTH])
        h = int(stats[idx, cv2.CC_STAT_HEIGHT])
        area = int(stats[idx, cv2.CC_STAT_AREA])
        if area < MIN_AREA:
            continue
        bbox_area = w * h
        if not bbox_area:
            continue
        rectangularity = area / bbox_area
        if rectangularity < MIN_RECTANGULARITY:
            continue

        component = (labels == idx).astype(np.uint8)
        metrics = _component_metrics(clean_rgb, component, x, y, w, h)
        if not metrics:
            continue
        kind = _classify(metrics)
        if not kind:
            continue
        suspects.append({
            'component_id': idx,
            'type': kind,
            'bbox': [x, y, w, h],
            'area': area,
            'rectangularity': rectangularity,
            **metrics,
            '_component': component,
        })
    return suspects


def _save_atomic(image: Image.Image, target: Path) -> None:
    suffix = target.suffix or '.png'
    fd, tmp_name = tempfile.mkstemp(prefix=f'.{target.stem}.level2-', suffix=suffix, dir=target.parent)
    os.close(fd)
    tmp = Path(tmp_name)
    try:
        image.save(tmp)
        os.replace(tmp, target)
    finally:
        if tmp.exists():
            tmp.unlink()


def refine(source_dir: Path, output_dir: Path) -> dict:
    source_dir = source_dir.resolve()
    output_dir = output_dir.resolve()
    sources = sorted(
        p for p in source_dir.iterdir()
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
    )
    if not sources:
        raise ValueError('Nível II: nenhuma imagem fonte encontrada.')

    analysis: list[tuple[Path, Path, Path, Image.Image, Image.Image, list[dict]]] = []
    total_components = 0
    type_counts = {'TYPE_A': 0, 'TYPE_B': 0}

    for source in sources:
        clean_path = _single_artifact(output_dir, source.stem, 'clean')
        mask_path = _single_artifact(output_dir, source.stem, 'mask')
        original = Image.open(source).convert('RGB')
        level1 = Image.open(clean_path).convert('RGB')
        if original.size != level1.size:
            raise RuntimeError(
                f'Nível II: dimensões divergentes em {source.name}: '
                f'original={original.size}, clean={level1.size}'
            )
        mask_bin = _load_mask(mask_path)
        clean_rgb = np.asarray(level1)
        if mask_bin.shape != clean_rgb.shape[:2]:
            raise RuntimeError(
                f'Nível II: máscara incompatível em {source.name}: '
                f'mask={mask_bin.shape}, clean={clean_rgb.shape[:2]}'
            )
        suspects = _detect_suspects(clean_rgb, mask_bin)
        for suspect in suspects:
            total_components += 1
            type_counts[suspect['type']] += 1
        analysis.append((source, clean_path, mask_path, original, level1, suspects))

    model = None
    device_name = None
    model_path = None
    if total_components:
        model_path = _find_model()
        os.environ['LAMA_MODEL'] = str(model_path)
        device = torch.device('mps') if torch.backends.mps.is_available() else torch.device('cpu')
        device_name = str(device)
        model = SimpleLama(device=device)

    page_reports = []
    pages_level2 = 0

    for source, clean_path, mask_path, original, level1, suspects in analysis:
        if not suspects:
            page_reports.append({
                'source': source.name,
                'clean': clean_path.name,
                'mask': mask_path.name,
                'level2': False,
                'components': [],
            })
            continue

        pages_level2 += 1
        original_np = np.asarray(original)
        # CRÍTICO: parte do resultado já limpo pelo Nível I. Assim o Nível II
        # não reintroduz textos removidos em componentes não suspeitos.
        final_np = np.asarray(level1).copy()
        height, width = original_np.shape[:2]
        serializable = []

        for suspect in suspects:
            x, y, w, h = suspect['bbox']
            component = suspect['_component']
            x1 = max(0, x - PADDING)
            y1 = max(0, y - PADDING)
            x2 = min(width, x + w + PADDING)
            y2 = min(height, y + h + PADDING)

            original_crop = Image.fromarray(original_np[y1:y2, x1:x2])
            component_crop = component[y1:y2, x1:x2]
            mask_crop = Image.fromarray((component_crop * 255).astype(np.uint8), mode='L')
            result = model(original_crop, mask_crop)
            if result.size != original_crop.size:
                result = result.crop((0, 0, original_crop.width, original_crop.height))

            result_np = np.asarray(result)
            local = component_crop > 0
            if result_np.shape[:2] != local.shape:
                raise RuntimeError(
                    f'Nível II: saída LaMa incompatível em {source.name}: '
                    f'lama={result_np.shape[:2]}, mask={local.shape}'
                )
            target = final_np[y1:y2, x1:x2]
            target[local] = result_np[local]
            final_np[y1:y2, x1:x2] = target

            serializable.append({
                k: v for k, v in suspect.items() if k != '_component'
            })

        _save_atomic(Image.fromarray(final_np), clean_path)
        page_reports.append({
            'source': source.name,
            'clean': clean_path.name,
            'mask': mask_path.name,
            'level2': True,
            'components': serializable,
        })

    return {
        'schema_version': 1,
        'algorithm': 'textoff_level2_v3_lama_local_v1',
        'detector': 'textoff_v3',
        'inpainter': 'anime-manga-big-lama',
        'model_path': str(model_path) if model_path else None,
        'device': device_name,
        'pages_analyzed': len(sources),
        'pages_level2': pages_level2,
        'components_level2': total_components,
        'type_counts': type_counts,
        'thresholds': {
            'min_area': MIN_AREA,
            'min_rectangularity': MIN_RECTANGULARITY,
            'type_a_min_std': TYPE_A_MIN_STD,
            'type_b_max_std': TYPE_B_MAX_STD,
            'type_b_min_context_range': TYPE_B_MIN_CONTEXT_RANGE,
            'type_b_max_internal_mean': TYPE_B_MAX_INTERNAL_MEAN,
            'band': BAND,
            'padding': PADDING,
        },
        'pages': page_reports,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Texto Off — Nível II (Detector V3 + LaMa localizado)')
    parser.add_argument('--source-dir', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--report', required=True, type=Path)
    args = parser.parse_args()

    if not args.source_dir.is_dir():
        parser.error(f'Pasta fonte não encontrada: {args.source_dir}')
    if not args.output_dir.is_dir():
        parser.error(f'Pasta do Nível I não encontrada: {args.output_dir}')

    report = refine(args.source_dir, args.output_dir)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print(
        'Texto Off — Nível II: '
        f"{report['pages_level2']}/{report['pages_analyzed']} página(s), "
        f"{report['components_level2']} componente(s) refinado(s).",
        flush=True,
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
