"""Render planner-approved Level III intervals from original page sources."""
import os
import tempfile
from pathlib import Path

from PIL import Image

from processamento.unificacao_imagens import image_stitcher as v3


def source_spans(infos: list, start: int, end: int) -> list[dict]:
    spans, cursor = [], int(start)
    for info in infos:
        low, high = max(start, info.global_start), min(end, info.global_end)
        if low >= high:
            continue
        if low != cursor:
            raise ValueError("Fontes não cobrem continuamente o intervalo do Nível III.")
        spans.append({"file": info.path.name, "global_start": info.global_start,
                      "global_end": info.global_end,
                      "source_y_start": low - info.global_start,
                      "source_y_end": high - info.global_start})
        cursor = high
    if cursor != end:
        raise ValueError("Fontes não cobrem integralmente o intervalo do Nível III.")
    return spans


def render_source_interval(chapter: Path, infos: list, start: int, end: int) -> Image.Image:
    width = infos[0].width
    image = Image.new("RGB", (width, end - start), "white")
    cursor = start
    for span in source_spans(infos, start, end):
        if span["global_start"] + span["source_y_start"] != cursor:
            raise ValueError("Intervalo sem cobertura contínua nas fontes.")
        with Image.open(chapter / span["file"]) as source:
            source.load()
            if source.width != width:
                raise ValueError("Larguras incompatíveis nas imagens-fonte.")
            crop = source.convert("RGB").crop((0, span["source_y_start"], width, span["source_y_end"]))
            image.paste(crop, (0, cursor - start))
        cursor = span["global_start"] + span["source_y_end"]
    if cursor != end:
        raise ValueError("As fontes não cobrem integralmente o intervalo renderizado.")
    return image


def _save(image: Image.Image, path: Path) -> None:
    descriptor, name = tempfile.mkstemp(prefix=".am3-", suffix=".png", dir=path.parent)
    os.close(descriptor)
    temporary = Path(name)
    try:
        image.save(temporary, format="PNG", optimize=False)
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def materialize_level3(chapter: Path, infos: list, intervals: list, stage: Path) -> list[dict]:
    stage.mkdir(parents=True, exist_ok=False)
    artifacts, created = [], []
    try:
        for item in intervals:
            start, end = int(item["global_start"]), int(item["global_end"])
            spans = source_spans(infos, start, end)
            base = Path(v3.page_range_output_name_from_spans(spans, start, end)).stem
            name = f"{base}-l3-{start}-{end}.png"
            path = stage / name
            _save(render_source_interval(chapter, infos, start, end), path)
            created.append(path)
            with Image.open(path) as saved:
                if saved.height != end - start:
                    raise ValueError("Altura materializada divergente do intervalo.")
                width = saved.width
            artifacts.append({**item, "file": name, "global_start": start,
                              "global_end": end, "height": end - start,
                              "width": width, "source_spans": spans,
                              "source_stage": "level3"})
    except Exception:
        for path in created:
            path.unlink(missing_ok=True)
        raise
    return artifacts
