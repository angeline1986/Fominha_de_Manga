"""Validation helpers for the manual batch PDF generator."""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

from PIL import Image, UnidentifiedImageError


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff"}
PDF_MIN_UNITS = 3.0
PDF_MAX_UNITS = 14400.0
DEFAULT_DPI = 96.0


@dataclass(frozen=True)
class ImageMetadata:
    path: Path
    width: int
    height: int
    format: str
    mode: str
    pdf_width: float
    pdf_height: float


@dataclass
class ValidationResult:
    ok: bool
    image_files: list[Path] = field(default_factory=list)
    metadata: list[ImageMetadata] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    expected_total: int | None = None

    @property
    def image_count(self) -> int:
        return len(self.image_files)


@dataclass
class PdfValidationResult:
    ok: bool
    path: Path
    page_count: int | None = None
    errors: list[str] = field(default_factory=list)


_PAGE_RE = re.compile(r"^page-(\d+)$", re.IGNORECASE)
_PDF_PAGE_RE = re.compile(rb"/Type\s*/Page(?!s)\b")


def natural_key(path: Path) -> list[object]:
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", path.name)]


def list_supported_images(chapter_dir: Path) -> list[Path]:
    if not chapter_dir.exists() or not chapter_dir.is_dir():
        return []
    return sorted(
        (
            path
            for path in chapter_dir.iterdir()
            if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
        ),
        key=natural_key,
    )


def page_number(path: Path) -> int | None:
    match = _PAGE_RE.match(path.stem)
    if not match:
        return None
    return int(match.group(1))


def _dpi_axis(value: object) -> float:
    try:
        dpi = float(value)
    except (TypeError, ValueError):
        return DEFAULT_DPI
    if not math.isfinite(dpi) or dpi <= 0:
        return DEFAULT_DPI
    return dpi


def _image_dpi(info: dict[str, object]) -> tuple[float, float]:
    value = info.get("dpi")
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)) and len(value) >= 2:
        return _dpi_axis(value[0]), _dpi_axis(value[1])
    return DEFAULT_DPI, DEFAULT_DPI


def pdf_units_for_pixels(pixels: int, dpi: float) -> float:
    return pixels * 72.0 / dpi


def _validate_page_sequence(image_files: Sequence[Path]) -> list[str]:
    numbers = [page_number(path) for path in image_files]
    if not numbers or any(number is None for number in numbers):
        return []

    actual = sorted(number for number in numbers if number is not None)
    expected = list(range(1, actual[-1] + 1))
    missing = [number for number in expected if number not in actual]
    if not missing:
        return []

    missing_text = ", ".join(f"page-{number:03d}" for number in missing)
    return [f"Sequência de páginas incompleta: faltando {missing_text}."]


def _image_metadata(path: Path) -> ImageMetadata:
    with Image.open(path) as image:
        image.load()
        x_dpi, y_dpi = _image_dpi(image.info)
        width, height = image.size
        return ImageMetadata(
            path=path,
            width=width,
            height=height,
            format=image.format or "unknown",
            mode=image.mode,
            pdf_width=pdf_units_for_pixels(width, x_dpi),
            pdf_height=pdf_units_for_pixels(height, y_dpi),
        )


def validate_chapter_images(chapter_dir: Path, expected_total: int | None = None) -> ValidationResult:
    image_files = list_supported_images(chapter_dir)
    result = ValidationResult(ok=True, image_files=image_files, expected_total=expected_total)

    if not image_files:
        result.errors.append("Nenhuma imagem compatível encontrada no capítulo.")

    if expected_total is not None and len(image_files) != expected_total:
        result.errors.append(
            f"Total de imagens divergente: esperado {expected_total}, encontrado {len(image_files)}."
        )

    result.errors.extend(_validate_page_sequence(image_files))

    for image_path in image_files:
        try:
            metadata = _image_metadata(image_path)
        except (OSError, UnidentifiedImageError) as exc:
            result.errors.append(f"Imagem ilegível: {image_path.name} ({exc}).")
            continue

        result.metadata.append(metadata)
        if not (PDF_MIN_UNITS <= metadata.pdf_width <= PDF_MAX_UNITS) or not (
            PDF_MIN_UNITS <= metadata.pdf_height <= PDF_MAX_UNITS
        ):
            result.errors.append(
                "Imagem incompatível com os limites do PDF/img2pdf: "
                f"{image_path.name} ({metadata.width}x{metadata.height}, "
                f"{metadata.format}, {metadata.mode}) gera "
                f"{metadata.pdf_width:.2f}x{metadata.pdf_height:.2f} unidades PDF."
            )

    result.ok = not result.errors
    return result


def count_pdf_pages(pdf_path: Path) -> int:
    data = pdf_path.read_bytes()
    return len(_PDF_PAGE_RE.findall(data))


def validation_report_path(chapter_dir: Path) -> Path:
    """Return the diagnostic report path for a chapter."""
    chapter = Path(chapter_dir)

    if chapter.parent.name == "IMG":
        manga_dir = chapter.parent.parent
    else:
        manga_dir = chapter.parent

    return manga_dir / "reports" / f"{chapter.name}.validation.json"


def _metadata_payload(metadata: Sequence[ImageMetadata]) -> list[dict[str, object]]:
    return [
        {
            "file": item.path.name,
            "width": item.width,
            "height": item.height,
            "format": item.format,
            "mode": item.mode,
            "pdf_width": round(item.pdf_width, 2),
            "pdf_height": round(item.pdf_height, 2),
        }
        for item in metadata
    ]


def write_validation_report(
    chapter_dir: Path,
    issue_type: str,
    *,
    message: str,
    validation: ValidationResult | None = None,
    pdf_validation: PdfValidationResult | None = None,
) -> Path:
    """Persist structured evidence for a chapter/PDF divergence."""
    chapter = Path(chapter_dir)
    report = validation_report_path(chapter)
    report.parent.mkdir(parents=True, exist_ok=True)

    payload: dict[str, object] = {
        "chapter": chapter.name,
        "issue_type": issue_type,
        "message": message,
        "pdf_generated": bool(
            pdf_validation is not None
            and pdf_validation.path.exists()
        ),
    }

    if validation is not None:
        payload["images"] = {
            "expected": validation.expected_total,
            "found": validation.image_count,
            "errors": list(validation.errors),
            "metadata": _metadata_payload(validation.metadata),
        }

    if pdf_validation is not None:
        payload["pdf"] = {
            "path": str(pdf_validation.path),
            "expected_pages": (
                validation.image_count
                if validation is not None
                else None
            ),
            "found_pages": pdf_validation.page_count,
            "errors": list(pdf_validation.errors),
            "size_bytes": (
                pdf_validation.path.stat().st_size
                if pdf_validation.path.exists()
                else None
            ),
        }

    temporary = report.with_name(f"{report.name}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(report)

    return report


def validate_pdf_output(pdf_path: Path, expected_pages: int) -> PdfValidationResult:
    result = PdfValidationResult(ok=True, path=pdf_path)

    if not pdf_path.exists():
        result.errors.append("PDF não foi criado.")
    elif pdf_path.stat().st_size <= 0:
        result.errors.append("PDF criado está vazio.")
    else:
        data = pdf_path.read_bytes()
        if not data.startswith(b"%PDF"):
            result.errors.append("Arquivo gerado não parece ser um PDF válido.")
        result.page_count = len(_PDF_PAGE_RE.findall(data))
        if result.page_count != expected_pages:
            result.errors.append(
                f"Quantidade de páginas do PDF divergente: esperado {expected_pages}, "
                f"encontrado {result.page_count}."
            )

    result.ok = not result.errors
    return result
