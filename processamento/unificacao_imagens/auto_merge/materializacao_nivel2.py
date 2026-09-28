"""Render only Level II planner-approved intervals into a fresh stage."""
import os
import tempfile
from pathlib import Path

from PIL import Image

from processamento.unificacao_imagens import image_stitcher as v3


def _spans(infos: list, start: int, end: int) -> list[dict]:
    result = []
    for info in infos:
        low, high = max(start, info.global_start), min(end, info.global_end)
        if low < high:
            result.append({
                "file": info.path.name,
                "global_start": info.global_start,
                "global_end": info.global_end,
                "source_y_start": low - info.global_start,
                "source_y_end": high - info.global_start,
            })
    return result


def _render(chapter: Path, infos: list, start: int, end: int) -> Image.Image:
    width = infos[0].width
    canvas = Image.new("RGB", (width, end - start), "white")
    cursor = start
    for span in _spans(infos, start, end):
        if span["global_start"] + span["source_y_start"] != cursor:
            raise ValueError("Intervalo sem cobertura contínua nas fontes.")
        path = chapter / span["file"]
        with Image.open(path) as source:
            source.load()
            if source.width != width:
                raise ValueError("Larguras incompatíveis nas imagens-fonte.")
            crop = source.convert("RGB").crop((0, span["source_y_start"], width, span["source_y_end"]))
            canvas.paste(crop, (0, cursor - start))
        cursor = span["global_start"] + span["source_y_end"]
    if cursor != end:
        raise ValueError("As fontes não cobrem integralmente o intervalo planejado.")
    return canvas


def _save(image: Image.Image, path: Path) -> None:
    descriptor, name = tempfile.mkstemp(prefix=".am2-", suffix=".png", dir=path.parent)
    os.close(descriptor)
    temporary = Path(name)
    try:
        image.save(temporary, format="PNG", optimize=False)
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def materialize_level2(chapter: Path, infos: list, plans: list, stage: Path) -> list[dict]:
    stage.mkdir(parents=True, exist_ok=False)
    artifacts, created, used_names = [], [], set()
    try:
        for entry in plans:
            for start, end in entry["plan"].get("resolved_intervals") or []:
                spans = _spans(infos, int(start), int(end))
                name = v3.unique_merge_output_name(spans, int(start), int(end), used_names)
                path = stage / name
                _save(_render(chapter, infos, int(start), int(end)), path)
                created.append(path)
                with Image.open(path) as saved:
                    saved.load()
                    if saved.height != int(end) - int(start):
                        raise ValueError("Altura materializada divergente do intervalo.")
                artifacts.append({
                    "file": name,
                    "global_start": int(start),
                    "global_end": int(end),
                    "height": int(end) - int(start),
                    "width": saved.width,
                    "source_segment_id": entry["segment_id"],
                    "source_spans": spans,
                    "stage": "level2",
                })
    except Exception:
        for path in created:
            path.unlink(missing_ok=True)
        raise
    return artifacts
