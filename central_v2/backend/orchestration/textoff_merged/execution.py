"""Run Cleaner V2 for the original Merged and isolated Level I stages."""
from pathlib import Path

from processamento.unificacao_imagens import image_stitcher as v3
from .cleaner import run_cleaner_v2

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


def execute_merged(manga: Path, chapters: list[str], progress, preflight=None,
                   *, output_stage: str = "MERGED", include_legacy_level2: bool = True) -> list[dict]:
    """Run Cleaner V2 over official MERGEs into an explicitly named stage."""
    if output_stage not in {"MERGED", "MERGED_NIVEL_I"}:
        raise ValueError("Destino de Texto Off inválido.")
    validate_selection(manga, chapters)
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
            result = run_cleaner_v2(
                images,
                manga / "FLUXO_SECUNDARIO" / "04_TEXTO_OFF" / output_stage / name,
                source_stage="MERGE", progress_job=_CleanerProgress(progress, name, index, len(chapters)),
                chapter_name=name, level1_only=not include_legacy_level2,
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


def execute_merged_level1(manga: Path, chapters: list[str], progress, preflight=None) -> list[dict]:
    """Run only Merged Nível I into its isolated output tree."""
    return execute_merged(
        manga, chapters, progress, preflight,
        output_stage="MERGED_NIVEL_I", include_legacy_level2=False,
    )


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
