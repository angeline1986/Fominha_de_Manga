#!/usr/bin/env python3
"""Root menu hub for projects under Fominha_de_Manga."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Sequence

from image_stitcher import run_merge_flow
from image_stitcher_review import run_merge_review_flow
from bubble_cleaner_flow import run_clean_flow
from pdf_divergence_review import run_divergence_review
from pdf_batch_validation import (
    IMAGE_EXTENSIONS,
    validate_chapter_images,
    validate_pdf_output,
    write_validation_report,
)


ROOT_DIR = Path(__file__).resolve().parent
MANGAGO_DIR = ROOT_DIR / "mangago_downloader"
MANGAGO_OUTPUT_DIR = MANGAGO_DIR / "output"
HEX = {
    "text": "#2c3e50",
    "separator": "#ffd166",
    "sec_download": "#ef476f",
    "item_download": "#ff8a5c",
    "sec_pdf": "#06d6a0",
    "item_pdf": "#118ab2",
    "number": "#7209b7",
    "prompt": "#4361ee",
    "success": "#06d6a0",
    "warning": "#ffd166",
    "error": "#ef476f",
    "muted": "#6c757d",
}


@dataclass(frozen=True)
class MenuItem:
    number: int
    label: str
    description: str
    action: Callable[[], None]
    color_key: str


@dataclass(frozen=True)
class MenuSection:
    title: str
    items: tuple[MenuItem, ...]
    color_key: str


def _supports_color() -> bool:
    return (
        os.environ.get("NO_COLOR") is None
        and sys.stdout.isatty()
        and os.environ.get("TERM", "") != "dumb"
    )


USE_COLOR = _supports_color()


def _ansi(hex_color: str, text: object, bold: bool = False) -> str:
    if not USE_COLOR:
        return str(text)
    value = hex_color.lstrip("#")
    r, g, b = int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)
    weight = "1;" if bold else ""
    return f"\033[{weight}38;2;{r};{g};{b}m{text}\033[0m"


def c(key: str, text: object, bold: bool = False) -> str:
    return _ansi(HEX[key], text, bold=bold)


def print_option(number: int, label: str, description: str = "", color_key: str = "text") -> None:
    suffix = f" {description}" if description else ""
    print(f"  {c('number', str(number)+'.', bold=True)} {c(color_key, f'{label:<22}')}{suffix}")


def ask_number(prompt: str, valid: Iterable[int] | None = None) -> int:
    valid_set = set(valid) if valid is not None else None
    while True:
        raw = input(c("prompt", prompt, bold=True)).strip()
        try:
            choice = int(raw)
        except ValueError:
            print("Opção inválida.")
            continue
        if valid_set is not None and choice not in valid_set:
            print("Opção inválida.")
            continue
        return choice


def resolve_root_dir() -> Path:
    return ROOT_DIR


def resolve_mangago_output_dir() -> Path:
    return MANGAGO_OUTPUT_DIR


def build_mangago_web_command() -> tuple[list[str], Path, dict[str, str]]:
    if not MANGAGO_DIR.exists():
        raise FileNotFoundError("Módulo mangago_downloader não encontrado.")

    venv_bin = MANGAGO_DIR / ".venv" / "bin" / "mangago-downloader-web"
    command = [str(venv_bin)] if venv_bin.exists() else [sys.executable, "-m", "webapp.server"]
    env = os.environ.copy()
    env.setdefault("MANGAGO_LOG_LEVEL", "INFO")
    return command, MANGAGO_DIR, env


def open_mangago_web() -> None:
    try:
        command, cwd, env = build_mangago_web_command()
    except FileNotFoundError as exc:
        print(c("error", f"Falha: {exc}"))
        return

    print(c("success", "Abrindo servidor Web do Mangago Downloader..."))
    print(c("muted", f"└─ {cwd}"))
    subprocess.run(command, cwd=cwd, env=env, check=False)



def open_processing_web() -> None:
    server = ROOT_DIR / "processing_web.py"
    if not server.is_file():
        print(c("error", "Central de Processamento não encontrada."))
        return
    print(c("success", "Abrindo Central de Processamento Web..."))
    print(c("muted", "└─ http://127.0.0.1:8766"))
    subprocess.run([sys.executable, str(server)], cwd=ROOT_DIR, check=False)

def _natural_key(path: Path) -> list[object]:
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", path.name)]


def _has_images(directory: Path) -> bool:
    return any(path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS for path in directory.iterdir())


def list_manga_dirs(output_dir: Path = MANGAGO_OUTPUT_DIR) -> list[Path]:
    if not output_dir.exists():
        return []

    mangas: list[Path] = []
    for provider_name in ("comix", "mangago"):
        provider_dir = output_dir / provider_name
        if not provider_dir.is_dir():
            continue

        mangas.extend(
            child
            for child in provider_dir.iterdir()
            if child.is_dir()
        )

    return sorted(mangas, key=lambda path: (_natural_key(path.parent), _natural_key(path)))


def list_chapter_dirs(manga_dir: Path) -> list[Path]:
    img_dir = manga_dir / "IMG"
    if not img_dir.exists():
        return []

    return sorted(
        (
            path
            for path in img_dir.iterdir()
            if path.is_dir() and _has_images(path)
        ),
        key=_natural_key,
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


def _import_convert_to_pdf() -> Callable[[str], str | None]:
    if not MANGAGO_DIR.exists():
        raise FileNotFoundError("Módulo mangago_downloader não encontrado.")
    mangago_path = str(MANGAGO_DIR)
    if mangago_path not in sys.path:
        sys.path.insert(0, mangago_path)
    from src.converter import convert_to_pdf

    return convert_to_pdf


def _pdf_path(chapter_dir: Path) -> Path:
    if chapter_dir.parent.name == "IMG":
        manga_dir = chapter_dir.parent.parent
        return manga_dir / "PDF" / chapter_dir.name / f"{chapter_dir.name}.pdf"

    return chapter_dir / f"{chapter_dir.name}.pdf"


def _completion_marker_path(chapter_dir: Path) -> Path:
    return chapter_dir / ".download-complete.json"


def _in_progress_marker_path(chapter_dir: Path) -> Path:
    return chapter_dir / ".download-in-progress.json"


def _expected_pages_from_marker(chapter_dir: Path) -> int | None:
    marker = _completion_marker_path(chapter_dir)
    if not marker.is_file():
        return None

    try:
        payload = json.loads(marker.read_text(encoding="utf-8"))
        if payload.get("status") != "completed":
            return None
        expected = int(payload.get("expected_pages") or 0)
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None

    return expected if expected > 0 else None


def run_pdf_batch(chapters: Sequence[Path], regenerate_existing: bool = False) -> dict[str, list[Path | tuple[Path, str]] | int]:
    convert_to_pdf = _import_convert_to_pdf()
    summary: dict[str, list[Path | tuple[Path, str]] | int] = {
        "selected": len(chapters),
        "generated": [],
        "skipped": [],
        "failed": [],
        "validation_failed": [],
        "generation_failed": [],
        "problems": [],
    }

    for chapter_dir in chapters:
        pdf_path = _pdf_path(chapter_dir)
        if pdf_path.exists() and not regenerate_existing:
            summary["skipped"].append(chapter_dir)
            print(c("warning", f"PDF existente: {chapter_dir.name}"))
            continue

        in_progress_marker = _in_progress_marker_path(chapter_dir)
        complete_marker = _completion_marker_path(chapter_dir)

        if in_progress_marker.is_file():
            message = (
                "Download deste capítulo ainda está em andamento. "
                "A geração do PDF foi bloqueada."
            )
            failure = (chapter_dir, message)
            summary["validation_failed"].append(failure)
            summary["failed"].append(failure)
            summary["problems"].append(failure)
            write_validation_report(
                chapter_dir,
                "download_not_completed",
                message=message,
            )
            print(c("error", f"PDF bloqueado: {chapter_dir.name} - {message}"))
            continue

        expected_pages = _expected_pages_from_marker(chapter_dir)

        if complete_marker.is_file() and expected_pages is None:
            message = (
                "Estado de conclusão do capítulo está inválido ou ilegível. "
                "A geração do PDF foi bloqueada."
            )
            failure = (chapter_dir, message)
            summary["validation_failed"].append(failure)
            summary["failed"].append(failure)
            summary["problems"].append(failure)
            write_validation_report(
                chapter_dir,
                "download_state_invalid",
                message=message,
            )
            print(c("error", f"PDF bloqueado: {chapter_dir.name} - {message}"))
            continue

        if expected_pages is not None:
            validation = validate_chapter_images(
                chapter_dir,
                expected_total=expected_pages,
            )
        else:
            # Compatibilidade com capítulos baixados antes da adoção
            # dos marcadores persistentes de estado.
            validation = validate_chapter_images(chapter_dir)
        if not validation.ok:
            message = "; ".join(validation.errors)
            failure = (chapter_dir, message)
            summary["validation_failed"].append(failure)
            summary["failed"].append(failure)
            summary["problems"].append(failure)
            write_validation_report(
                chapter_dir,
                "image_validation_failed",
                message=message,
                validation=validation,
            )
            print(c("error", f"Falha de validação: {chapter_dir.name} - {message}"))
            continue

        print(c("prompt", f"Gerando PDF: {chapter_dir.name}"))
        try:
            created = convert_to_pdf(str(chapter_dir))
        except Exception as exc:  # Defensive: keep batch processing remaining chapters.
            failure = (chapter_dir, str(exc))
            summary["generation_failed"].append(failure)
            summary["failed"].append(failure)
            summary["problems"].append(failure)
            print(c("error", f"Falha de geração: {chapter_dir.name} - {exc}"))
            continue

        if not created:
            failure = (chapter_dir, "convert_to_pdf retornou vazio")
            summary["generation_failed"].append(failure)
            summary["failed"].append(failure)
            summary["problems"].append(failure)
            print(c("error", f"Falha de geração: {chapter_dir.name}"))
            continue

        pdf_validation = validate_pdf_output(Path(created), validation.image_count)
        if not pdf_validation.ok:
            message = "; ".join(pdf_validation.errors)
            failure = (chapter_dir, message)
            summary["generation_failed"].append(failure)
            summary["failed"].append(failure)
            summary["problems"].append(failure)

            if (
                pdf_validation.page_count is not None
                and pdf_validation.page_count != validation.image_count
            ):
                issue_type = "pdf_page_count_mismatch"
            else:
                issue_type = "pdf_validation_failed"

            write_validation_report(
                chapter_dir,
                issue_type,
                message=message,
                validation=validation,
                pdf_validation=pdf_validation,
            )

            print(c("error", f"Falha de validação do PDF: {chapter_dir.name} - {message}"))
            continue

        summary["generated"].append(chapter_dir)
        print(c("success", f"Sucesso: {Path(created).name}"))

    return summary


def manual_pdf_flow(output_dir: Path = MANGAGO_OUTPUT_DIR) -> None:
    if not MANGAGO_DIR.exists():
        print(c("error", "Módulo mangago_downloader não encontrado."))
        return

    if not output_dir.exists():
        print(c("error", "Nenhum output encontrado para o Mangago Downloader."))
        print(c("muted", f"└─ {output_dir}"))
        return

    providers: list[Path] = []
    for provider_name in ("comix", "mangago"):
        provider_dir = output_dir / provider_name
        if provider_dir.is_dir():
            providers.append(provider_dir)

    if not providers:
        print(c("error", "Nenhum provider com downloads encontrado."))
        print(c("muted", f"└─ {output_dir}"))
        return

    print_header("GERAR PDFS")
    for index, provider_dir in enumerate(providers, start=1):
        print_option(index, provider_dir.name.capitalize())
        print()
    print(f"  {c('number', '0.', bold=True)} Voltar")

    provider_choice = ask_number(
        "\nSelecione uma opção › ",
        range(0, len(providers) + 1),
    )
    if provider_choice == 0:
        return

    provider_dir = providers[provider_choice - 1]

    mangas = sorted(
        (path for path in provider_dir.iterdir() if path.is_dir()),
        key=_natural_key,
    )

    if not mangas:
        print(c("error", "Nenhuma obra baixada encontrada."))
        print(c("muted", f"└─ {provider_dir}"))
        return

    print_header(provider_dir.name.upper())
    for index, manga_dir in enumerate(mangas, start=1):
        print_option(index, manga_dir.name)
        print()
    print(f"  {c('number', '0.', bold=True)} Voltar")

    manga_choice = ask_number(
        "\nSelecione uma opção › ",
        range(0, len(mangas) + 1),
    )
    if manga_choice == 0:
        return

    manga_dir = mangas[manga_choice - 1]

    chapters = list_chapter_dirs(manga_dir)

    print_header(manga_dir.name.upper())
    print_option(1, "Todos os capítulos")
    print()
    print_option(2, "Somente capítulos sem PDF")
    print()
    print_option(3, "Selecionar capítulos")
    print()
    print_option(4, "Validar divergências")
    print()
    print(f"  {c('number', '0.', bold=True)} Voltar")

    mode = ask_number("\nSelecione uma opção › ", range(0, 5))
    if mode == 0:
        return

    if mode == 4:
        run_divergence_review(manga_dir, ask_number=ask_number, print_header=print_header, c=c)
        return

    if not chapters:
        print(c("error", "Nenhum capítulo com imagens encontrado."))
        print(c("muted", f"└─ {manga_dir / 'IMG'}"))
        return

    selected = chapters

    if mode == 2:
        selected = [
            chapter
            for chapter in chapters
            if not _pdf_path(chapter).exists()
        ]

    elif mode == 3:
        for index, chapter_dir in enumerate(chapters, start=1):
            marker = "PDF" if _pdf_path(chapter_dir).exists() else ""
            print(
                f"  {c('number', str(index)+'.', bold=True)} "
                f"{chapter_dir.name:<32} "
                f"{c('muted', marker)}"
            )

        raw = input(
            c(
                "prompt",
                "\nCapítulos (1,2,5 ou 1,3,5-9,12 ou todos) › ",
                bold=True,
            )
        )

        selected = [
            chapters[index - 1]
            for index in parse_selection(raw, len(chapters))
        ]

    if not selected:
        print(c("warning", "Nenhum capítulo sem PDF encontrado."))
        return

    existing = [
        chapter
        for chapter in selected
        if _pdf_path(chapter).exists()
    ]

    regenerate = False

    if existing:
        print(c("warning", "Alguns capítulos já possuem PDF."))

        for chapter in existing:
            print(c("muted", f"└─ {chapter.name}"))

        regenerate = (
            ask_number(
                "\nRegenerar PDFs existentes? 1=Sim 2=Não › ",
                {1, 2},
            )
            == 1
        )

    summary = run_pdf_batch(
        selected,
        regenerate_existing=regenerate,
    )

    print_header("RESUMO")
    print(c("muted", f"Selecionados: {summary['selected']}"))
    print(c("success", f"Gerados: {len(summary['generated'])}"))
    print(c("warning", f"Já existentes: {len(summary['skipped'])}"))
    print(
        c(
            "error" if summary["validation_failed"] else "success",
            f"Falha de validação: {len(summary['validation_failed'])}",
        )
    )
    print(
        c(
            "error" if summary["generation_failed"] else "success",
            f"Falha de geração: {len(summary['generation_failed'])}",
        )
    )

    if summary["problems"]:
        print(c("error", "Problemas:"))
        for chapter, message in summary["problems"]:
            print(c("muted", f"└─ {chapter.name}: {message}"))



def manual_merge_flow(output_dir: Path = MANGAGO_OUTPUT_DIR) -> None:
    run_merge_flow(
        output_dir,
        ask_number=ask_number,
        print_header=print_header,
        print_option=print_option,
        c=c,
    )


def manual_clean_flow(output_dir: Path = MANGAGO_OUTPUT_DIR) -> None:
    run_clean_flow(output_dir, ask_number=ask_number, print_header=print_header, print_option=print_option, c=c)

def manual_merge_review_flow(output_dir: Path = MANGAGO_OUTPUT_DIR) -> None:
    run_merge_review_flow(
        output_dir,
        ask_number=ask_number,
        print_header=print_header,
        print_option=print_option,
        c=c,
    )


def print_header(title: str = "FOMINHA DE MANGA") -> None:
    print()
    print(c("number", title, bold=True))
    print(c("separator", "━" * 50))


def build_menu() -> tuple[MenuSection, ...]:
    return (
        MenuSection(
            "DOWNLOAD DE MANGÁS",
            (MenuItem(1, "Mangago Downloader", "Abrir servidor Web", open_mangago_web, "item_download"),),
            "sec_download",
        ),
        MenuSection(
            "PROCESSAMENTO",
            (MenuItem(6, "Central de Processamento", "Abrir servidor Web", open_processing_web, "item_pdf"),),
            "sec_pdf",
        ),
        MenuSection(
            "PDF",
            (MenuItem(2, "Gerar PDFs", "Gerar PDFs de capítulos baixados", manual_pdf_flow, "item_pdf"),),
            "sec_pdf",
        ),
        MenuSection(
            "FLUXO SECUNDÁRIO",
            (
                MenuItem(3, "Unificar imagens", "Gerar imagens verticais pelo Merge V3", manual_merge_flow, "item_pdf"),
                MenuItem(4, "Limpar balões", "Limpar textos de balões com Bubble Cleaner V3.5", manual_clean_flow, "item_pdf"),
                MenuItem(5, "Tratar merges pendentes", "Propor e revisar exceções sem alterar o Merge V3", manual_merge_review_flow, "item_pdf"),
            ),
            "sec_pdf",
        ),
    )


def print_main_menu(sections: Sequence[MenuSection]) -> None:
    print_header()
    print()
    for section in sections:
        print(c(section.color_key, f"● {section.title}", bold=True))
        print()
        for item in section.items:
            print_option(item.number, item.label, item.description, item.color_key)
            print()
        print()
    print(c("separator", "━" * 50))
    print(f"  {c('number', '0.', bold=True)} Sair")
    print()


def main() -> None:
    sections = build_menu()
    actions = {item.number: item.action for section in sections for item in section.items}
    valid = set(actions) | {0}

    while True:
        print_main_menu(sections)
        choice = ask_number("Selecione uma opção › ", valid)
        if choice == 0:
            print(c("success", "Até logo."))
            return
        actions[choice]()


if __name__ == "__main__":
    main()
