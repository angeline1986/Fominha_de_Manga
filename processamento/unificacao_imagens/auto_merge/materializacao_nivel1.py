"""Render safe Level I intervals into an isolated, previously empty stage."""
import os
import tempfile
from pathlib import Path

from PIL import Image

from processamento.unificacao_imagens import image_stitcher as v3
from processamento.unificacao_imagens.auto_merge.planejamento_nivel1 import (
    Level1Plan, validate_plan,
)


def _validate_sources(infos: list, total_height: int) -> int:
    expected = 0
    width = None
    for info in infos:
        if info.global_start != expected or info.global_end <= info.global_start:
            raise ValueError("As imagens-fonte não formam uma sequência contínua.")
        if info.height != info.global_end - info.global_start:
            raise ValueError("Altura declarada da imagem-fonte divergente.")
        if width is None:
            width = info.width
        elif width != info.width:
            raise ValueError("As larguras das imagens-fonte são divergentes.")
        expected = info.global_end
    if expected != total_height or not width:
        raise ValueError("As fontes não cobrem a altura planejada.")
    return width


def _source_spans(infos: list, start: int, end: int) -> list[dict]:
    spans = []
    for info in infos:
        low = max(start, info.global_start)
        high = min(end, info.global_end)
        if low < high:
            spans.append({
                "file": info.path.name,
                "global_start": info.global_start,
                "global_end": info.global_end,
                "source_y_start": low - info.global_start,
                "source_y_end": high - info.global_start,
            })
    return spans


def _render_interval(infos: list, start: int, end: int, width: int) -> Image.Image:
    canvas = Image.new("RGB", (width, end - start), "white")
    expected_y = start
    for info in infos:
        low = max(start, info.global_start)
        high = min(end, info.global_end)
        if low >= high:
            continue
        if low != expected_y:
            raise ValueError("Intervalo sem cobertura contínua nas imagens-fonte.")
        with Image.open(info.path) as source:
            source.load()
            if source.size != (width, info.height):
                raise ValueError(f"Dimensão da fonte divergente: {info.path.name}.")
            crop = source.convert("RGB").crop((0, low - info.global_start, width, high - info.global_start))
            canvas.paste(crop, (0, low - start))
        expected_y = high
    if expected_y != end:
        raise ValueError("O intervalo não foi coberto integralmente pelas fontes.")
    return canvas


def _save_new_image(image: Image.Image, destination: Path) -> None:
    fd, temporary_name = tempfile.mkstemp(prefix=".am1-", suffix=".png", dir=destination.parent)
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        image.save(temporary, format="PNG", optimize=False)
        os.link(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def materialize_safe_intervals(plan: Level1Plan, infos: list, output_dir: Path) -> list[dict]:
    """Write only planner-approved intervals; never replace existing stage files."""
    validate_plan(plan)
    width = _validate_sources(infos, plan.total_height)
    output_dir = Path(output_dir)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(exist_ok=False)
    artifacts = []
    created = []
    try:
        for interval in plan.intervals:
            if interval.status != "safe":
                continue
            spans = _source_spans(infos, interval.start, interval.end)
            name = v3.page_range_output_name_from_spans(spans, interval.start, interval.end)
            destination = v3.ensure_unique_output_path(output_dir, name)
            image = _render_interval(infos, interval.start, interval.end, width)
            _save_new_image(image, destination)
            created.append(destination)
            with Image.open(destination) as saved:
                saved.load()
                if saved.size != (width, interval.end - interval.start):
                    raise ValueError(f"Dimensão de saída divergente: {name}.")
            artifacts.append({
                "file": name,
                "global_start": interval.start,
                "global_end": interval.end,
                "width": width,
                "height": interval.end - interval.start,
                "sources": spans,
            })
    except Exception:
        for path in created:
            path.unlink(missing_ok=True)
        raise
    return artifacts
