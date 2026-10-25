"""Resolve a Laboratory source to one official final page by manifest identity."""
import json
from pathlib import Path

from .stages import stage_root


def final_target(manga: Path, source_path: Path, source: dict) -> tuple[str, str]:
    chapter, page = source.get("chapter"), source.get("filename")
    if not source_path.is_relative_to(manga) or not isinstance(page, str):
        return chapter, page
    names = {page}
    if page.endswith("_clean.png"):
        names.add(page[:-10] + ".png")
    root = stage_root(manga, "CONSOLIDADO_FINAL", read_legacy=False).resolve()
    matches = []
    if root.is_dir():
        for manifest in root.glob("*/json/final-manifest.json"):
            if not manifest.resolve().is_relative_to(root):
                continue
            try:
                data = json.loads(manifest.read_text(encoding="utf-8"))
            except (OSError, ValueError, UnicodeError):
                continue
            if not isinstance(data, dict):
                continue
            pages = data.get("pages")
            if (data.get("chapter") != manifest.parent.parent.name
                    or data.get("provider") != manga.parent.name
                    or data.get("manga") != manga.name or not isinstance(pages, dict)):
                continue
            matches.extend((data["chapter"], name) for name in names if name in pages)
    if (chapter, page) in matches:
        return chapter, page
    source_chapter = _source_chapter(manga, source_path, source)
    identified = [(item_chapter, item_page) for item_chapter, item_page in matches
                  if item_chapter == source_chapter]
    if len(identified) == 1:
        return identified[0]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise ValueError("Página presente em mais de um capítulo no Consolidado Final; selecione a origem IMG ou MERGE.")
    return chapter, page


def _source_chapter(manga: Path, path: Path, source: dict) -> str | None:
    parts = path.relative_to(manga).parts
    prefix = ("FLUXO_SECUNDARIO", "04_TEXTO_OFF")
    if parts[:2] != prefix:
        return None
    if (len(parts) == 6 and parts[2] == "04_AUTO_CLEANER_CHECK"
            and parts[4] == "images" and parts[5] == source.get("filename")
            and source.get("chapter") == "images"):
        return parts[3]
    if (len(parts) == 6 and parts[2] in {"01_AUTO_CLEANER", "TO_MERGED_NIVEL_I"}
            and parts[4] == "clean" and parts[5] == source.get("filename")
            and source.get("chapter") == "clean"):
        return parts[3]
    if (len(parts) == 7 and parts[2] == "05_AUTO_CLEANER_TRANSPARENCIA"
            and parts[3] in {"BASICA", "NORMAL", "LEGADA"}
            and parts[5] == "clean" and parts[6] == source.get("filename")
            and source.get("chapter") == "clean"):
        return parts[4]
    return None
