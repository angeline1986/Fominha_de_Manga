"""Resolve the persisted Auto-Cleaner Glass (Básica) image stage."""
from pathlib import Path
from central_v2.backend.state.work_layout import textoff_root

from central_v2.backend.orchestration.textoff_merged.stages import (
    LEVEL2, stage_chapter, stage_root,
)
from central_v2.backend.state.sorting import natural_sort_key


def glass_chapter(manga, chapter):
    if not chapter or Path(chapter).name != chapter or chapter in {".", ".."}:
        raise ValueError("Capítulo inválido.")
    work = Path(manga).resolve()
    stage = stage_chapter(work, LEVEL2, chapter).resolve()
    clean = (stage / "clean").resolve()
    if not stage.is_relative_to(work) or not clean.is_relative_to(stage) or not clean.is_dir():
        raise ValueError("Saída do Auto-Cleaner Glass indisponível.")
    return clean


def glass_chapter_names(manga):
    work = Path(manga).resolve()
    target = textoff_root(work) / "05_AUTO_CLEANER_TRANSPARENCIA/BASICA"
    roots = (stage_root(work, LEVEL2), target)
    names = {folder.name for root in roots if root.is_dir()
             for folder in root.iterdir() if folder.is_dir()
             and folder.resolve().is_relative_to(work)}
    return sorted(names, key=natural_sort_key)


def check_page_for_glass(filename):
    return filename[:-10] + ".png" if filename.endswith("_clean.png") else None
