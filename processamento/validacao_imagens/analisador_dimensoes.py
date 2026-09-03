#!/usr/bin/env python3
"""
Analisador independente de dimensões das imagens baixadas.

- Analisa imagens originais sem modificar nenhum arquivo.
- Calcula a largura dominante por capítulo.
- Aceita pequenas variações com tolerância percentual configurável.
- Destaca exceções de dimensão.
- Gera relatórios TXT e JSON.
- Não altera Auto-Merge, Auto-Merge Nível II ou qualquer outro fluxo.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from PIL import Image

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


@dataclass
class ImageAnalysis:
    file: str
    width: int
    height: int
    difference_px: int
    difference_percent: float
    classification: str


@dataclass
class ChapterAnalysis:
    chapter: str
    image_count: int
    dominant_width: int | None
    min_width: int | None
    max_width: int | None
    width_counts: dict[str, int]
    tolerance_percent: float
    tolerance_px: float | None
    status: str
    within_tolerance: int
    exceptions: int
    images: list[ImageAnalysis]


def natural_key(value: str):
    parts = re.split(r"(\d+)", value)
    return tuple(int(p) if p.isdigit() else p.lower() for p in parts)


def iter_images(chapter_dir: Path):
    return sorted(
        (
            p for p in chapter_dir.iterdir()
            if p.is_file()
            and p.suffix.lower() in IMAGE_EXTENSIONS
            and p.name.lower().startswith("page-")
        ),
        key=lambda p: natural_key(p.name),
    )


def analyze_chapter(chapter_dir: Path, tolerance_percent: float) -> ChapterAnalysis:
    dimensions = []
    unreadable = []

    for image_path in iter_images(chapter_dir):
        try:
            with Image.open(image_path) as img:
                width, height = img.size
            dimensions.append((image_path.name, int(width), int(height)))
        except Exception as exc:
            unreadable.append((image_path.name, str(exc)))

    if not dimensions:
        return ChapterAnalysis(
            chapter=chapter_dir.name,
            image_count=0,
            dominant_width=None,
            min_width=None,
            max_width=None,
            width_counts={},
            tolerance_percent=tolerance_percent,
            tolerance_px=None,
            status="SEM_IMAGENS_VALIDAS",
            within_tolerance=0,
            exceptions=0,
            images=[],
        )

    widths = [w for _, w, _ in dimensions]
    counts = Counter(widths)
    max_count = max(counts.values())
    dominant_width = min(w for w, count in counts.items() if count == max_count)
    tolerance_px = dominant_width * tolerance_percent / 100.0

    image_results = []
    within = 0
    exceptions = 0

    for name, width, height in dimensions:
        diff_px = abs(width - dominant_width)
        diff_percent = (diff_px / dominant_width * 100.0) if dominant_width else 0.0

        if diff_px == 0:
            classification = "PADRAO"
            within += 1
        elif diff_percent <= tolerance_percent:
            classification = "DENTRO_TOLERANCIA"
            within += 1
        else:
            classification = "EXCECAO_DIMENSAO"
            exceptions += 1

        image_results.append(
            ImageAnalysis(
                file=name,
                width=width,
                height=height,
                difference_px=diff_px,
                difference_percent=round(diff_percent, 3),
                classification=classification,
            )
        )

    status = "OK" if exceptions == 0 and not unreadable else "REQUER_ANALISE"

    return ChapterAnalysis(
        chapter=chapter_dir.name,
        image_count=len(dimensions),
        dominant_width=dominant_width,
        min_width=min(widths),
        max_width=max(widths),
        width_counts={str(k): v for k, v in sorted(counts.items())},
        tolerance_percent=tolerance_percent,
        tolerance_px=round(tolerance_px, 2),
        status=status,
        within_tolerance=within,
        exceptions=exceptions,
        images=image_results,
    )


def chapter_dirs(root: Path, selected: list[str] | None):
    if selected:
        found = []
        for chapter in selected:
            path = root / str(chapter)
            if path.is_dir():
                found.append(path)
            else:
                print(f"[AVISO] Capítulo não encontrado: {path}")
        return found

    return sorted((p for p in root.iterdir() if p.is_dir()), key=lambda p: natural_key(p.name))


def render_text(root: Path, results: list[ChapterAnalysis], tolerance_percent: float) -> str:
    lines = [
        "ANÁLISE DE DIMENSÕES DAS IMAGENS",
        "=" * 78,
        f"Origem: {root}",
        f"Tolerância aceita: ±{tolerance_percent:.2f}% da largura dominante",
        f"Gerado em: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "Classificação:",
        "  PADRAO             = largura igual à dominante",
        "  DENTRO_TOLERANCIA  = diferença <= tolerância configurada",
        "  EXCECAO_DIMENSAO   = diferença > tolerância; apenas sinalizada",
        "",
        "Nenhuma imagem é modificada, excluída, movida ou redimensionada.",
        "",
        f"Resumo: {len(results)} capítulo(s) analisado(s) · "
        f"{sum(r.status == 'REQUER_ANALISE' for r in results)} requer(em) análise",
        "",
    ]

    for result in results:
        lines += [
            "=" * 78,
            f"CAPÍTULO {result.chapter} — {result.status}",
            "=" * 78,
        ]

        if result.dominant_width is None:
            lines += ["Nenhuma imagem válida encontrada.", ""]
            continue

        lines += [
            f"Imagens: {result.image_count}",
            f"Largura dominante: {result.dominant_width}px",
            f"Faixa observada: {result.min_width}px – {result.max_width}px",
            f"Tolerância em pixels: ±{result.tolerance_px}px",
            f"Distribuição: {result.width_counts}",
            f"Dentro do padrão/tolerância: {result.within_tolerance} · Exceções: {result.exceptions}",
        ]

        exceptions = [img for img in result.images if img.classification == "EXCECAO_DIMENSAO"]
        if exceptions:
            lines += ["", "EXCEÇÕES:"]
            for img in exceptions:
                lines.append(
                    f"  {img.file:<24} {img.width}x{img.height} · "
                    f"diferença {img.difference_px}px ({img.difference_percent:.3f}%)"
                )
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Analisa dimensões de imagens baixadas sem modificar os arquivos."
    )
    parser.add_argument(
        "pasta_img",
        type=Path,
        help="Pasta IMG da obra, contendo uma subpasta por capítulo.",
    )
    parser.add_argument(
        "--capitulos",
        nargs="+",
        help="Opcional: capítulos específicos, ex.: --capitulos 60 61 62 63",
    )
    parser.add_argument(
        "--tolerancia",
        type=float,
        default=3.0,
        help="Margem percentual aceita em relação à largura dominante. Padrão: 3%%.",
    )
    parser.add_argument(
        "--saida",
        type=Path,
        default=None,
        help="Diretório de saída. Padrão: <obra>/FLUXO_SECUNDARIO/ANALISE_DIMENSOES",
    )

    args = parser.parse_args()
    root = args.pasta_img.expanduser().resolve()

    if not root.is_dir():
        parser.error(f"Pasta IMG não encontrada: {root}")
    if not 0 <= args.tolerancia <= 100:
        parser.error("--tolerancia deve estar entre 0 e 100.")

    dirs = chapter_dirs(root, args.capitulos)
    if not dirs:
        parser.error("Nenhum capítulo encontrado para análise.")

    results = [analyze_chapter(ch, args.tolerancia) for ch in dirs]

    output_dir = (
        args.saida.expanduser().resolve()
        if args.saida is not None
        else root.parent / "FLUXO_SECUNDARIO" / "ANALISE_DIMENSOES"
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    txt_path = output_dir / f"analise_dimensoes_{timestamp}.txt"
    json_path = output_dir / f"analise_dimensoes_{timestamp}.json"

    txt_path.write_text(render_text(root, results, args.tolerancia), encoding="utf-8")

    payload = {
        "schema_version": 1,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source": str(root),
        "tolerance_percent": args.tolerancia,
        "summary": {
            "chapters_analyzed": len(results),
            "chapters_ok": sum(r.status == "OK" for r in results),
            "chapters_requiring_analysis": sum(r.status == "REQUER_ANALISE" for r in results),
        },
        "chapters": [
            {
                **asdict(result),
                "images": [asdict(img) for img in result.images],
            }
            for result in results
        ],
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print("")
    print("ANÁLISE CONCLUÍDA")
    print(f"TXT : {txt_path}")
    print(f"JSON: {json_path}")
    print("")
    for result in results:
        print(
            f"Cap. {result.chapter}: {result.status} · "
            f"dominante={result.dominant_width}px · exceções={result.exceptions}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
