"""Use cases for querying and running TextOff on official MERGE images."""
from __future__ import annotations

import json
from pathlib import Path

from processamento.unificacao_imagens import image_stitcher as v3


def _clean_manifest(manga: Path, chapter: str) -> dict:
    path = manga / "FLUXO_SECUNDARIO" / "04_TEXTO_OFF" / "MERGED" / chapter / "clean-manifest.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def _listing_merge_artifacts(chapter: Path) -> list[Path]:
    """Read MERGE metadata and check file presence without decoding image pixels."""
    manifest_path = v3.merge_manifest_path(chapter)
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        outputs = manifest.get("outputs")
        expected_count = int(manifest.get("merged_images") or 0)
        source_height = int(manifest.get("source_total_height") or 0)
    except (OSError, ValueError, TypeError, AttributeError):
        return []
    if not isinstance(outputs, list) or not outputs or len(outputs) != expected_count:
        return []

    output_dir = manifest_path.parent
    artifacts = []
    position = 0
    for item in outputs:
        if not isinstance(item, dict):
            return []
        filename = str(item.get("file") or "")
        try:
            start, end = int(item["global_start"]), int(item["global_end"])
            height = int(item.get("height", end - start))
        except (KeyError, TypeError, ValueError):
            return []
        if (not filename or Path(filename).name != filename or start != position
                or end <= start or height != end - start):
            return []
        artifact = output_dir / filename
        if not artifact.is_file():
            return []
        artifacts.append(artifact)
        position = end
    if position != source_height:
        return []
    return artifacts


def query_merged(manga: Path) -> dict:
    """Project official MERGE availability and current TextOff manifests."""
    rows = []
    root = manga / "IMG"
    chapters = sorted(
        (path for path in root.iterdir() if path.is_dir()),
        key=lambda path: v3.natural_key(path / "page-1.png"),
    ) if root.is_dir() else []
    for chapter in chapters:
        files = _listing_merge_artifacts(chapter)
        merged = bool(files)
        manifest = _clean_manifest(manga, chapter.name)
        expected = [path.name for path in files]
        processed = (
            manifest.get("source_stage") == "MERGE"
            and manifest.get("integrity_ok") is True
            and manifest.get("source_artifacts") == expected
            and manifest.get("outputs_total") == len(expected)
        )
        rows.append({
            "chapter": chapter.name,
            "merge_valid": merged,
            "merge_count": len(files),
            "cleaned": processed,
            "clean_count": int(manifest.get("outputs_total") or 0),
            "selectable": merged and bool(files),
        })
    return {"chapters": rows, "total": len(rows)}


def validate_selection(manga: Path, chapters: object) -> list[str]:
    if not isinstance(chapters, list) or not chapters or len(chapters) > 100:
        raise ValueError("Selecione de 1 a 100 capítulos.")
    if any(not isinstance(name, str) or not name or Path(name).name != name for name in chapters):
        raise ValueError("A seleção contém capítulos inválidos.")
    if len(set(chapters)) != len(chapters):
        raise ValueError("A seleção contém capítulos repetidos.")
    root = manga / "IMG"
    available = {path.name: path for path in root.iterdir() if path.is_dir()} if root.is_dir() else {}
    if any(name not in available for name in chapters):
        raise ValueError("A seleção contém capítulos fora da obra.")
    for name in chapters:
        chapter = available[name]
        if not v3.is_chapter_merged(chapter) or not v3.merge_artifact_files(v3.merge_output_dir(chapter)):
            raise ValueError(f"Capítulo {name} não possui MERGE oficial válido.")
    return chapters


def execute_merged(manga: Path, chapters: list[str], progress, preflight=None) -> list[dict]:
    """Run the existing Cleaner V2 contract over selected official MERGEs."""
    validate_selection(manga, chapters)
    from processamento.limpeza_baloes.cleaner_v2.integration import clean_chapter

    results = []
    for index, name in enumerate(chapters, 1):
        if preflight:
            preflight()
        chapter = manga / "IMG" / name
        if not v3.is_chapter_merged(chapter):
            results.append({"chapter": name, "status": "failed", "error": "MERGE oficial inválido ou alterado antes da execução."})
            progress(name, {"stage": "done", "percent": round(index * 100 / len(chapters)),
                            "completed": index, "total": len(chapters),
                            "message": f"Capítulo {name}: MERGE oficial inválido ou alterado."})
            continue
        images = v3.merge_artifact_files(v3.merge_output_dir(chapter))
        if not images:
            results.append({"chapter": name, "status": "failed", "error": "MERGE oficial sem imagens."})
            progress(name, {"stage": "done", "percent": round(index * 100 / len(chapters)),
                            "completed": index, "total": len(chapters),
                            "message": f"Capítulo {name}: MERGE oficial sem imagens."})
            continue
        progress(name, {
            "stage": "clean", "percent": round((index - 1) * 100 / len(chapters)),
            "completed": index - 1, "total": len(chapters),
            "message": f"Capítulo {index}/{len(chapters)}: iniciando Cleaner V2 nos merges oficiais.",
        })
        try:
            result = clean_chapter(
                images,
                manga / "FLUXO_SECUNDARIO" / "04_TEXTO_OFF" / "MERGED" / name,
                source_stage="MERGE", progress_job=_CleanerProgress(progress, name, index, len(chapters)),
                chapter_name=name,
            )
            results.append({"chapter": name, **result})
        except Exception as exc:
            results.append({"chapter": name, "status": "failed", "error": str(exc)})
        progress(name, {
            "stage": "done", "percent": round(index * 100 / len(chapters)),
            "completed": index, "total": len(chapters),
            "message": f"Capítulo {name}: processamento finalizado.",
        })
    return results


class _CleanerProgress:
    def __init__(self, notify, chapter, index, total):
        self.notify, self.chapter = notify, chapter
        self.index, self.total = index, total
        self.value, self.detail = 0.0, "Preparando Cleaner V2"

    def _emit(self):
        ratio = max(0.0, min(1.0, self.value))
        percent = round((self.index - 1 + ratio) * 100 / self.total)
        self.notify(self.chapter, {
            "stage": "clean", "percent": percent,
            "completed": self.index - 1, "total": self.total,
            "message": self.detail,
        })

    @property
    def progress_value(self):
        return self.value

    @progress_value.setter
    def progress_value(self, value):
        self.value = float(value or 0)
        self._emit()

    @property
    def progress_detail(self):
        return self.detail

    @progress_detail.setter
    def progress_detail(self, value):
        self.detail = str(value or "")
        self._emit()

    @property
    def message(self):
        return self.detail

    @message.setter
    def message(self, value):
        self.detail = str(value or "")
        self._emit()
