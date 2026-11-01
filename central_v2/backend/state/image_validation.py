"""Estado da análise de dimensões das imagens originais na Central V2."""

from dataclasses import asdict
import json
import os
from pathlib import Path
import tempfile

from central_v2.backend.state.sorting import natural_sort_key
from central_v2.backend.state.work_layout import images_root, secondary_root
from processamento.validacao_imagens.analisador_dimensoes import analyze_chapter, iter_images


def _record_path(manga: Path) -> Path:
    return secondary_root(manga) / "ANALISE_DIMENSOES" / "validacao_v2.json"


def _fingerprint(directory: Path) -> list[list]:
    images = list(iter_images(directory))
    if any(path.is_symlink() for path in images):
        raise ValueError("Imagens vinculadas fora da obra não podem ser validadas.")
    return [[path.name, path.stat().st_size, path.stat().st_mtime_ns] for path in images]


def _load(manga: Path) -> dict:
    path = _record_path(manga)
    if not path.is_file():
        return {"schema_version": 1, "chapters": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1 or not isinstance(data.get("chapters"), dict):
        raise ValueError("Registro de validação incompatível.")
    return data


def _save(manga: Path, data: dict) -> None:
    path = _record_path(manga)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                     prefix=".validacao-v2-", suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def chapter_directories(manga: Path) -> dict[str, Path]:
    root = images_root(manga)
    if not root.is_dir():
        return {}
    if not root.resolve().is_relative_to(manga.resolve()):
        raise ValueError("Diretório IMG fora da obra.")
    return {path.name: path for path in sorted(root.iterdir(), key=lambda x: natural_sort_key(x.name))
            if path.is_dir() and not path.is_symlink() and list(iter_images(path))}


def validate_chapters(manga: Path, chapters: object) -> list[str]:
    available = chapter_directories(manga)
    if not isinstance(chapters, list) or not chapters or len(chapters) > len(available):
        raise ValueError("Selecione ao menos um capítulo válido.")
    if any(not isinstance(name, str) or name not in available for name in chapters):
        raise ValueError("Há capítulos inválidos na seleção.")
    if len(set(chapters)) != len(chapters):
        raise ValueError("Há capítulos repetidos na seleção.")
    return chapters


def read_chapter(manga: Path, chapter: str) -> dict | None:
    directory = chapter_directories(manga).get(chapter)
    if directory is None:
        return None
    record = _load(manga)["chapters"].get(chapter)
    if not isinstance(record, dict) or record.get("fingerprint") != _fingerprint(directory):
        return None
    return record


def catalog(manga: Path, provider: str, name: str) -> dict:
    saved = _load(manga)["chapters"]
    rows = []
    for chapter, directory in chapter_directories(manga).items():
        record = saved.get(chapter)
        fingerprint = _fingerprint(directory)
        valid = isinstance(record, dict) and record.get("fingerprint") == fingerprint
        analysis = record.get("analysis", {}) if valid else {}
        status = "pending"
        if analysis:
            status = ("review" if analysis.get("exceptions", 0) else "attention") if analysis.get("status") != "OK" else (
                "applied" if record.get("applied_files") else "ok")
        rows.append({"chapter": chapter, "image_count": analysis.get("image_count", len(fingerprint)),
                     "dominant_width": analysis.get("dominant_width"),
                     "exceptions": analysis.get("exceptions"), "status": status,
                     "images": [image for image in analysis.get("images", [])
                                if image.get("classification") == "EXCECAO_DIMENSAO"],
                     "tolerance_percent": analysis.get("tolerance_percent")})
    return {"provider": provider, "manga": name, "chapters": rows}


def analyze(manga: Path, chapters: list[str], tolerance: float, progress=None) -> list[dict]:
    if not 0 <= tolerance <= 100:
        raise ValueError("A tolerância deve estar entre 0% e 100%.")
    directories = chapter_directories(manga)
    saved = _load(manga)
    results = []
    for index, chapter in enumerate(chapters, 1):
        directory = directories[chapter]
        fingerprint = _fingerprint(directory)
        analysis = asdict(analyze_chapter(directory, tolerance))
        previous = saved["chapters"].get(chapter, {})
        applied = previous.get("applied_files", []) if isinstance(previous, dict) and previous.get("fingerprint") == fingerprint else []
        saved["chapters"][chapter] = {
            "fingerprint": fingerprint, "analysis": analysis,
            "applied_files": applied,
        }
        _save(manga, saved)
        outcome = "review" if analysis["exceptions"] else ("attention" if analysis["status"] != "OK" else "ok")
        results.append({"chapter": chapter, "status": outcome,
                        "exceptions": analysis["exceptions"]})
        if progress:
            progress(chapter, {"completed": index, "total": len(chapters),
                               "percent": round(index * 100 / len(chapters)),
                               "message": f"Cap. {chapter}: {analysis['exceptions']} divergência(s)."})
    return results


def record_application(manga: Path, chapter: str, filename: str, tolerance: float) -> None:
    directory = chapter_directories(manga)[chapter]
    saved = _load(manga)
    previous = saved["chapters"][chapter]
    applied = list(dict.fromkeys([*previous.get("applied_files", []), filename]))
    saved["chapters"][chapter] = {
        "fingerprint": _fingerprint(directory),
        "analysis": asdict(analyze_chapter(directory, tolerance)),
        "applied_files": applied,
    }
    _save(manga, saved)
