#!/usr/bin/env python3
"""Official secondary-flow image stitcher based on the validated whitespace V3 algorithm.

Source of truth:
    <work>/IMG/<chapter>/page-NNN.ext

Derived output:
    <work>/FLUXO_SECUNDARIO/MERGE/<chapter>/merged-NNN.png
    <work>/FLUXO_SECUNDARIO/MERGE/<chapter>/merge-manifest.json

Safety guarantees:
- source images are never modified or deleted;
- target height is only a preference, never a hard cut;
- only horizontal whitespace bands >= 150px are eligible by default;
- if no eligible band exists near the target, search continues forward;
- no cut is forced without an eligible whitespace band;
- every source pixel is preserved exactly once and in order.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

import numpy as np
from PIL import Image, UnidentifiedImageError

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
PAGE_RE = re.compile(r"^page-(\d+)\.[^.]+$", re.IGNORECASE)
MERGED_RE = re.compile(r"^merged-(\d+)\.png$", re.IGNORECASE)

PAGE_RANGE_OUTPUT_RE = re.compile(
    r"^page-(\d+)(?:-(\d+))?\.png$",
    re.IGNORECASE,
)
SOURCE_PAGE_RE = re.compile(
    r"^page-(\d+)(?:\.[^.]+)?$",
    re.IGNORECASE,
)


def _source_page_number(value) -> int:
    name = Path(str(value)).name
    match = SOURCE_PAGE_RE.match(name)
    if not match:
        raise ValueError(
            f"Nome de página-fonte não reconhecido para nomenclatura do merge: {name}"
        )
    return int(match.group(1))


def page_range_output_name(first_page, last_page) -> str:
    first = _source_page_number(first_page)
    last = _source_page_number(last_page)
    if last < first:
        raise ValueError(f"Intervalo de páginas inválido: {first}..{last}")
    width = max(3, len(str(first)), len(str(last)))
    if first == last:
        return f"page-{first:0{width}d}.png"
    return f"page-{first:0{width}d}-{last:0{width}d}.png"


def page_range_output_name_from_sources(sources) -> str:
    items = list(sources or [])
    if not items:
        raise ValueError("Não há páginas-fonte para nomear o artefato.")
    def source_name(item):
        if isinstance(item, dict):
            return item.get("file")
        return item
    return page_range_output_name(
        source_name(items[0]),
        source_name(items[-1]),
    )


def page_range_output_name_from_spans(spans, start_y=None, end_y=None) -> str:
    selected = []
    for span in spans or []:
        if start_y is not None and end_y is not None:
            lo = int(span.get("global_start", 0))
            hi = int(span.get("global_end", 0))
            if max(int(start_y), lo) >= min(int(end_y), hi):
                continue
        selected.append(span)
    return page_range_output_name_from_sources(selected)


def merge_artifact_files(directory: Path) -> list[Path]:
    directory = Path(directory)
    files = []
    for candidate in directory.glob("*.png"):
        if PAGE_RANGE_OUTPUT_RE.match(candidate.name) or MERGED_RE.match(candidate.name):
            files.append(candidate)

    def key(path):
        m = PAGE_RANGE_OUTPUT_RE.match(path.name)
        if m:
            return (0, int(m.group(1)), int(m.group(2) or m.group(1)), path.name)
        m = MERGED_RE.match(path.name)
        return (1, int(m.group(1)) if m else 10**12, 0, path.name)

    return sorted(files, key=key)


def ensure_unique_output_path(directory: Path, filename: str) -> Path:
    path = Path(directory) / filename
    if path.exists():
        raise ValueError(
            f"Colisão de nomenclatura do merge: {filename}. "
            "Dois artefatos distintos não podem representar o mesmo intervalo de páginas."
        )
    return path


DEFAULT_TARGET_HEIGHT = 7000
DEFAULT_SEARCH_BEFORE = 1800
DEFAULT_SEARCH_AFTER = 2500
DEFAULT_MIN_CHUNK_HEIGHT = 3000
DEFAULT_MIN_WHITE_BAND = 150
DEFAULT_MAX_CHUNK_HEIGHT = 12000
DEFAULT_WHITE_RATIO = 0.985
DEFAULT_LIGHT_THRESHOLD = 245
DEFAULT_SAMPLE_WIDTH = 256


@dataclass(frozen=True)
class PageInfo:
    path: Path
    width: int
    height: int
    global_start: int
    global_end: int


@dataclass(frozen=True)
class WhiteBand:
    start: int
    end: int
    height: int
    white_ratio_mean: float


@dataclass(frozen=True)
class MergeResult:
    chapter_dir: Path
    output_dir: Path
    source_pages: int
    merged_images: int
    cuts: int
    manifest_path: Path


def natural_key(path: Path):
    match = PAGE_RE.match(path.name)
    return (int(match.group(1)) if match else math.inf, path.name.lower())


def list_pages(chapter_dir: Path) -> list[Path]:
    chapter_dir = Path(chapter_dir)
    if not chapter_dir.is_dir():
        return []
    return sorted(
        [
            path
            for path in chapter_dir.iterdir()
            if path.is_file()
            and path.suffix.lower() in IMAGE_EXTS
            and PAGE_RE.match(path.name)
        ],
        key=natural_key,
    )


def merge_output_dir(chapter_dir: Path) -> Path:
    """Return official secondary-flow merge path for IMG/<chapter>."""
    chapter = Path(chapter_dir)
    if chapter.parent.name != "IMG":
        raise ValueError(f"Capítulo fora da estrutura IMG esperada: {chapter}")
    manga_dir = chapter.parent.parent
    return manga_dir / "FLUXO_SECUNDARIO" / "MERGE" / chapter.name


def merge_manifest_path(chapter_dir: Path) -> Path:
    return merge_output_dir(chapter_dir) / "merge-manifest.json"


def is_chapter_merged(chapter_dir: Path) -> bool:
    chapter_dir = Path(chapter_dir)
    manifest = merge_manifest_path(chapter_dir)

    if not manifest.is_file():
        return False

    try:
        payload = json.loads(
            manifest.read_text(encoding="utf-8")
        )
        outputs = payload.get("outputs") or []
        expected = int(
            payload.get("merged_images") or len(outputs)
        )
    except (
        OSError,
        ValueError,
        TypeError,
        json.JSONDecodeError,
    ):
        return False

    if expected <= 0 or len(outputs) != expected:
        return False

    pages = list_pages(chapter_dir)

    if not pages:
        return False

    source_width = None
    source_total_height = 0

    try:
        for page in pages:
            with Image.open(page) as image:
                image.load()
                width, height = image.size

            if width <= 0 or height <= 0:
                return False

            if source_width is None:
                source_width = int(width)
            elif int(width) != source_width:
                return False

            source_total_height += int(height)
    except (OSError, UnidentifiedImageError):
        return False

    if source_width is None or source_total_height <= 0:
        return False

    try:
        manifest_total = int(
            payload.get("source_total_height")
        )
    except (TypeError, ValueError):
        return False

    if manifest_total != source_total_height:
        return False

    output_dir = manifest.parent
    expected_start = 0

    for item in outputs:
        try:
            filename = str(item["file"]).strip()
            start = int(item["global_start"])
            end = int(item["global_end"])
            declared_width = int(
                item.get("width", source_width)
            )
            declared_height = int(
                item.get("height", end - start)
            )
        except (
            KeyError,
            TypeError,
            ValueError,
        ):
            return False

        if not filename:
            return False

        if start != expected_start:
            return False

        if end <= start:
            return False

        interval_height = end - start

        if declared_width != source_width:
            return False

        if declared_height != interval_height:
            return False

        output_path = output_dir / filename

        if not output_path.is_file():
            return False

        try:
            with Image.open(output_path) as image:
                image.load()

                if image.size != (
                    source_width,
                    interval_height,
                ):
                    return False
        except (OSError, UnidentifiedImageError):
            return False

        expected_start = end

    if expected_start != source_total_height:
        return False

    validation = payload.get("validation")

    if isinstance(validation, dict):
        try:
            coverage_start = int(
                validation.get("coverage_start", 0)
            )
            coverage_end = int(
                validation.get(
                    "coverage_end",
                    source_total_height,
                )
            )
        except (TypeError, ValueError):
            return False

        if coverage_start != 0:
            return False

        if coverage_end != source_total_height:
            return False

    return True


def row_whiteness(
    image: Image.Image,
    *,
    sample_width: int,
    light_threshold: int,
) -> np.ndarray:
    gray = image.convert("L")
    width, height = gray.size
    if width > sample_width:
        gray = gray.resize((sample_width, height), Image.Resampling.BILINEAR)
    arr = np.asarray(gray, dtype=np.uint8)
    return (arr >= light_threshold).mean(axis=1)


def analyze_chapter(
    pages: list[Path],
    *,
    sample_width: int = DEFAULT_SAMPLE_WIDTH,
    light_threshold: int = DEFAULT_LIGHT_THRESHOLD,
    white_ratio_threshold: float = DEFAULT_WHITE_RATIO,
) -> tuple[list[PageInfo], list[WhiteBand], int, int]:
    infos: list[PageInfo] = []
    all_scores: list[np.ndarray] = []
    global_y = 0
    expected_width: int | None = None

    for path in pages:
        with Image.open(path) as image:
            image.load()
            width, height = image.size

            if expected_width is None:
                expected_width = width
            elif width != expected_width:
                raise ValueError(
                    f"Largura divergente: {path.name} tem {width}px; "
                    f"esperado {expected_width}px."
                )

            infos.append(PageInfo(path, width, height, global_y, global_y + height))
            all_scores.append(
                row_whiteness(
                    image,
                    sample_width=sample_width,
                    light_threshold=light_threshold,
                )
            )
            global_y += height

    scores = np.concatenate(all_scores) if all_scores else np.array([], dtype=float)
    is_white = scores >= white_ratio_threshold

    bands: list[WhiteBand] = []
    start: int | None = None
    for idx, value in enumerate(is_white):
        if value and start is None:
            start = idx
        elif not value and start is not None:
            if idx > start:
                bands.append(
                    WhiteBand(
                        start=start,
                        end=idx,
                        height=idx - start,
                        white_ratio_mean=float(scores[start:idx].mean()),
                    )
                )
            start = None

    if start is not None and len(is_white) > start:
        bands.append(
            WhiteBand(
                start=start,
                end=len(is_white),
                height=len(is_white) - start,
                white_ratio_mean=float(scores[start:].mean()),
            )
        )

    return infos, bands, global_y, int(expected_width or 0)


def page_at_y(infos: list[PageInfo], y: int) -> tuple[str, int]:
    for info in infos:
        if info.global_start <= y < info.global_end:
            return info.path.name, y - info.global_start
    last = infos[-1]
    return last.path.name, last.height


def choose_cuts(
    total_height: int,
    bands: list[WhiteBand],
    *,
    target_height: int = DEFAULT_TARGET_HEIGHT,
    search_before: int = DEFAULT_SEARCH_BEFORE,
    search_after: int = DEFAULT_SEARCH_AFTER,
    min_chunk_height: int = DEFAULT_MIN_CHUNK_HEIGHT,
    min_white_band: int = DEFAULT_MIN_WHITE_BAND,
    max_chunk_height: int = DEFAULT_MAX_CHUNK_HEIGHT,
) -> tuple[list[dict], list[dict]]:
    """Validated V3 cut strategy. Never forces a cut."""
    cuts: list[dict] = []
    decisions: list[dict] = []
    current = 0

    while total_height - current > target_height + search_after:
        target = current + target_height
        low = max(current + min_chunk_height, target - search_before)
        normal_high = min(total_height - min_chunk_height, target + search_after)
        hard_high = min(total_height - min_chunk_height, current + max_chunk_height)

        eligible: list[dict] = []
        rejected_in_range: list[dict] = []

        for band in bands:
            center = (band.start + band.end) // 2
            if center <= current + min_chunk_height:
                continue
            if center > hard_high:
                continue
            if center < low:
                continue

            item = {
                "center": center,
                "band_start": band.start,
                "band_end": band.end,
                "band_height": band.height,
                "band_white_ratio_mean": round(band.white_ratio_mean, 5),
                "distance_from_target": center - target,
                "inside_normal_window": bool(center <= normal_high),
            }

            if band.height < min_white_band:
                item["decision"] = "rejected"
                item["reason"] = "white_band_too_short"
                rejected_in_range.append(item)
                continue

            item["decision"] = "eligible"
            eligible.append(item)

        if not eligible:
            decisions.extend(rejected_in_range)
            break

        normal_candidates = [item for item in eligible if item["inside_normal_window"]]
        if normal_candidates:
            chosen = sorted(
                normal_candidates,
                key=lambda item: (
                    abs(item["distance_from_target"]),
                    -item["band_height"],
                    -item["band_white_ratio_mean"],
                ),
            )[0]
            chosen["selection_reason"] = "safe_band_near_target"
        else:
            chosen = sorted(eligible, key=lambda item: item["center"])[0]
            chosen["selection_reason"] = "next_safe_band_forward"

        decisions.extend(rejected_in_range)
        for item in eligible:
            if item["center"] == chosen["center"]:
                continue
            nonchosen = dict(item)
            nonchosen["decision"] = "not_selected"
            nonchosen["reason"] = (
                "another_safe_band_ranked_better"
                if nonchosen["inside_normal_window"]
                else "forward_candidate_not_needed"
            )
            decisions.append(nonchosen)

        chosen["decision"] = "selected"
        cuts.append(chosen)
        decisions.append(dict(chosen))
        current = chosen["center"]

    return cuts, decisions


def render_chunks(
    infos: list[PageInfo],
    cuts: list[dict],
    total_height: int,
    width: int,
    output_dir: Path,
) -> list[dict]:
    output_dir.mkdir(parents=True, exist_ok=True)
    boundaries = [0] + [cut["center"] for cut in cuts] + [total_height]
    outputs: list[dict] = []

    for index, (start_y, end_y) in enumerate(zip(boundaries, boundaries[1:]), start=1):
        chunk_h = end_y - start_y
        canvas = Image.new("RGB", (width, chunk_h), "white")
        sources: list[dict] = []

        for info in infos:
            overlap_start = max(start_y, info.global_start)
            overlap_end = min(end_y, info.global_end)
            if overlap_start >= overlap_end:
                continue

            local_top = overlap_start - info.global_start
            local_bottom = overlap_end - info.global_start
            paste_y = overlap_start - start_y

            with Image.open(info.path) as image:
                image = image.convert("RGB")
                piece = image.crop((0, local_top, width, local_bottom))
                canvas.paste(piece, (0, paste_y))

            sources.append(
                {
                    "file": info.path.name,
                    "source_crop": [0, local_top, width, local_bottom],
                    "destination_y": paste_y,
                }
            )

        out_name = page_range_output_name_from_sources(sources)
        out_path = ensure_unique_output_path(output_dir, out_name)
        canvas.save(out_path, "PNG", optimize=False)

        start_page, start_local = page_at_y(infos, start_y)
        end_page, end_local = page_at_y(infos, max(start_y, end_y - 1))
        outputs.append(
            {
                "file": out_name,
                "width": width,
                "height": chunk_h,
                "global_start": start_y,
                "global_end": end_y,
                "starts_at": {"page": start_page, "y": start_local},
                "ends_at": {"page": end_page, "y": end_local + 1},
                "sources": sources,
            }
        )

    return outputs


def validate_merge_outputs(
    *,
    outputs: list[dict],
    output_dir: Path,
    total_height: int,
    width: int,
    cuts: list[dict],
    min_white_band: int,
) -> list[str]:
    errors: list[str] = []
    if not outputs:
        return ["Nenhuma imagem unificada foi gerada."]

    expected_start = 0
    for index, item in enumerate(outputs, start=1):
        if item["global_start"] != expected_start:
            errors.append(f"Cobertura descontínua antes de {item['file']}.")
        if item["global_end"] <= item["global_start"]:
            errors.append(f"Intervalo inválido em {item['file']}.")
        expected_start = item["global_end"]

        path = output_dir / item["file"]
        if not path.is_file():
            errors.append(f"Saída ausente: {item['file']}.")
            continue
        try:
            with Image.open(path) as image:
                image.load()
                if image.size != (width, item["height"]):
                    errors.append(
                        f"Dimensão divergente em {item['file']}: "
                        f"{image.size[0]}x{image.size[1]}."
                    )
        except (OSError, UnidentifiedImageError) as exc:
            errors.append(f"Saída ilegível: {item['file']} ({exc}).")

    if expected_start != total_height:
        errors.append(
            f"Cobertura final divergente: esperado {total_height}px, obtido {expected_start}px."
        )

    for cut in cuts:
        if cut["band_height"] < min_white_band:
            errors.append(
                f"Corte inseguro em {cut['center']}px: faixa branca de {cut['band_height']}px."
            )

    return errors


def merge_chapter(
    chapter_dir: Path,
    *,
    target_height: int = DEFAULT_TARGET_HEIGHT,
    search_before: int = DEFAULT_SEARCH_BEFORE,
    search_after: int = DEFAULT_SEARCH_AFTER,
    min_chunk_height: int = DEFAULT_MIN_CHUNK_HEIGHT,
    min_white_band: int = DEFAULT_MIN_WHITE_BAND,
    max_chunk_height: int = DEFAULT_MAX_CHUNK_HEIGHT,
    white_ratio: float = DEFAULT_WHITE_RATIO,
    light_threshold: int = DEFAULT_LIGHT_THRESHOLD,
    sample_width: int = DEFAULT_SAMPLE_WIDTH,
) -> MergeResult:
    """Generate official merge for one chapter without touching source files."""
    chapter = Path(chapter_dir).expanduser().resolve()
    if not chapter.is_dir():
        raise ValueError(f"Pasta do capítulo não encontrada: {chapter}")

    pages = list_pages(chapter)
    if not pages:
        raise ValueError("Nenhuma imagem page-NNN encontrada.")

    output_dir = merge_output_dir(chapter)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(
            f"Merge já existente ou pasta de saída ocupada: {output_dir}"
        )

    infos, bands, total_height, width = analyze_chapter(
        pages,
        sample_width=sample_width,
        light_threshold=light_threshold,
        white_ratio_threshold=white_ratio,
    )
    cuts, decisions = choose_cuts(
        total_height,
        bands,
        target_height=target_height,
        search_before=search_before,
        search_after=search_after,
        min_chunk_height=min_chunk_height,
        min_white_band=min_white_band,
        max_chunk_height=max_chunk_height,
    )
    # Safety barrier: V3 never forces a cut. If the selected safe
    # boundaries would leave any chunk above the operational maximum,
    # abort before allocating/rendering an oversized Pillow canvas.
    boundaries = [0] + [cut["center"] for cut in cuts] + [total_height]
    oversized_chunks = [
        (start_y, end_y, end_y - start_y)
        for start_y, end_y in zip(boundaries, boundaries[1:])
        if end_y - start_y > max_chunk_height
    ]
    if oversized_chunks:
        start_y, end_y, chunk_h = oversized_chunks[0]
        raise RuntimeError(
            "Merge interrompido com segurança: a estratégia V3 não encontrou "
            f"uma faixa branca elegível antes de {max_chunk_height:,} px. "
            f"O próximo trecho teria {chunk_h:,} px "
            f"(intervalo global {start_y:,}–{end_y:,}). "
            "Nenhum corte foi forçado e nenhuma imagem gigante foi criada."
        )

    outputs = render_chunks(infos, cuts, total_height, width, output_dir)
    validation_errors = validate_merge_outputs(
        outputs=outputs,
        output_dir=output_dir,
        total_height=total_height,
        width=width,
        cuts=cuts,
        min_white_band=min_white_band,
    )
    if validation_errors:
        raise RuntimeError("; ".join(validation_errors))

    cut_payload: list[dict] = []
    for cut in cuts:
        page, local_y = page_at_y(infos, cut["center"])
        item = dict(cut)
        item["source_page"] = page
        item["source_y"] = local_y
        cut_payload.append(item)

    decision_payload: list[dict] = []
    for item in decisions:
        page, local_y = page_at_y(infos, item["center"])
        payload = dict(item)
        payload["source_page"] = page
        payload["source_y"] = local_y
        decision_payload.append(payload)

    manifest = {
        "schema_version": 1,
        "algorithm": "whitespace_v3",
        "source_dir": str(chapter),
        "output_dir": str(output_dir),
        "source_pages": len(pages),
        "source_width": width,
        "source_total_height": total_height,
        "merged_images": len(outputs),
        "parameters": {
            "target_height": target_height,
            "search_before": search_before,
            "search_after": search_after,
            "min_chunk_height": min_chunk_height,
            "min_white_band": min_white_band,
            "max_chunk_height": max_chunk_height,
            "white_ratio": white_ratio,
            "light_threshold": light_threshold,
            "sample_width": sample_width,
        },
        "white_bands_found_total": len(bands),
        "cuts": cut_payload,
        "decisions": decision_payload,
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
            "short_white_band_can_be_selected": False,
            "all_source_pixels_preserved_in_order": True,
        },
    }
    manifest_path = output_dir / "merge-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    return MergeResult(
        chapter_dir=chapter,
        output_dir=output_dir,
        source_pages=len(pages),
        merged_images=len(outputs),
        cuts=len(cuts),
        manifest_path=manifest_path,
    )


def _natural_name_key(path: Path) -> list[object]:
    return [
        int(part) if part.isdigit() else part.lower()
        for part in re.split(r"(\d+)", path.name)
    ]


def _has_pages(directory: Path) -> bool:
    return bool(list_pages(directory))


def list_chapters(manga_dir: Path) -> list[Path]:
    img_dir = Path(manga_dir) / "IMG"
    if not img_dir.is_dir():
        return []
    return sorted(
        [path for path in img_dir.iterdir() if path.is_dir() and _has_pages(path)],
        key=_natural_name_key,
    )


def parse_selection(raw: str, total: int) -> list[int]:
    value = raw.strip().lower()
    if value in {"todos", "todas", "all"}:
        return list(range(1, total + 1))
    selected: set[int] = set()
    for chunk in value.split(","):
        part = chunk.strip()
        if not part:
            continue
        if "-" in part:
            start_text, end_text = part.split("-", 1)
            start, end = int(start_text), int(end_text)
            if start > end:
                start, end = end, start
            selected.update(range(start, end + 1))
        else:
            selected.add(int(part))
    return sorted(number for number in selected if 1 <= number <= total)


def run_merge_flow(
    output_dir: Path,
    *,
    ask_number: Callable[[str, Iterable[int] | None], int],
    print_header: Callable[[str], None],
    print_option: Callable[[int, str, str, str], None],
    c: Callable[[str, object, bool], str],
) -> None:
    """Interactive root-menu flow. Menu only delegates; merge logic stays here."""
    output_root = Path(output_dir)
    providers = [
        output_root / provider
        for provider in ("comix", "mangago")
        if (output_root / provider).is_dir()
    ]
    if not providers:
        print(c("error", "Nenhum provider com downloads encontrado."))
        print(c("muted", f"└─ {output_root}"))
        return

    print_header("UNIFICAR IMAGENS")
    for index, provider_dir in enumerate(providers, start=1):
        print_option(index, provider_dir.name.capitalize(), "", "text")
        print()
    print(f"  {c('number', '0.', True)} Voltar")
    provider_choice = ask_number("\nSelecione uma opção › ", range(0, len(providers) + 1))
    if provider_choice == 0:
        return

    provider_dir = providers[provider_choice - 1]
    mangas = sorted(
        [path for path in provider_dir.iterdir() if path.is_dir() and (path / "IMG").is_dir()],
        key=_natural_name_key,
    )
    if not mangas:
        print(c("error", "Nenhuma obra com capítulos baixados encontrada."))
        return

    print_header(provider_dir.name.upper())
    for index, manga_dir in enumerate(mangas, start=1):
        print_option(index, manga_dir.name, "", "text")
        print()
    print(f"  {c('number', '0.', True)} Voltar")
    manga_choice = ask_number("\nSelecione uma opção › ", range(0, len(mangas) + 1))
    if manga_choice == 0:
        return

    manga_dir = mangas[manga_choice - 1]
    chapters = list_chapters(manga_dir)
    if not chapters:
        print(c("error", "Nenhum capítulo com imagens encontrado."))
        print(c("muted", f"└─ {manga_dir / 'IMG'}"))
        return

    print_header(manga_dir.name.upper())
    print_option(1, "Todos os capítulos", "", "text")
    print()
    print_option(2, "Ainda não unificados", "", "text")
    print()
    print_option(3, "Selecionar capítulos", "", "text")
    print()
    print(f"  {c('number', '0.', True)} Voltar")
    mode = ask_number("\nSelecione uma opção › ", range(0, 4))
    if mode == 0:
        return

    if mode == 2:
        selected = [chapter for chapter in chapters if not is_chapter_merged(chapter)]
    elif mode == 3:
        for index, chapter in enumerate(chapters, start=1):
            marker = "MERGE" if is_chapter_merged(chapter) else ""
            print(
                f"  {c('number', str(index)+'.', True)} "
                f"{chapter.name:<32} {c('muted', marker)}"
            )
        raw = input(
            c(
                "prompt",
                "\nCapítulos (1,2,5 ou 1,3,5-9,12 ou todos) › ",
                True,
            )
        )
        selected = [chapters[index - 1] for index in parse_selection(raw, len(chapters))]
    else:
        selected = chapters

    if not selected:
        print(c("warning", "Todos os capítulos já possuem merge."))
        return

    generated: list[MergeResult] = []
    skipped: list[Path] = []
    failed: list[tuple[Path, str]] = []

    for chapter in selected:
        if merge_output_dir(chapter).exists() and any(merge_output_dir(chapter).iterdir()):
            skipped.append(chapter)
            print(c("warning", f"Merge existente: {chapter.name}"))
            continue
        print(c("prompt", f"Unificando: {chapter.name}"))
        try:
            result = merge_chapter(chapter)
        except Exception as exc:
            failed.append((chapter, str(exc)))
            print(c("error", f"Falha: {chapter.name} - {exc}"))
            continue
        generated.append(result)
        print(
            c(
                "success",
                f"Sucesso: {chapter.name} · {result.source_pages} originais → "
                f"{result.merged_images} imagens unificadas",
            )
        )

    print_header("RESUMO DO MERGE")
    print(c("muted", f"Selecionados: {len(selected)}"))
    print(c("success", f"Gerados: {len(generated)}"))
    print(c("warning", f"Já existentes: {len(skipped)}"))
    print(c("error" if failed else "success", f"Falhas: {len(failed)}"))
    if failed:
        for chapter, message in failed:
            print(c("muted", f"└─ {chapter.name}: {message}"))
